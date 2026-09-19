# Query and node memory policy

The HTTP node and standalone supervisor accept `--memory-mb N`, defaulting to
256 MiB. The valid range is 1–1,048,576 MiB; zero does not disable accounting.
The HTTP owner chooses the limit. Requests cannot raise it. It applies to every
query lifetime, including source loading, startup shared-database validation,
compiled bundles, pagination and idle continuations.

```
./isobase-node --port 8081 --max-queries 8 --memory-mb 128
./query-supervisor 'query(between(1,5,X),X)' 2 --memory-mb 64
make memory-test
python3 memory_tests.py --seconds 60
```

## What is counted

`memory.h` measures the supervisor and its one worker and sums their current
usage. On macOS it uses `proc_pid_rusage(RUSAGE_INFO_V2).ri_phys_footprint`.
This is the kernel's physical-footprint accounting, not virtual address-space
size, peak RSS or GNU Prolog stack usage. It covers the charged memory of atoms,
source, dynamic clauses, Prolog stacks, C allocations and transport threads.
Clean shared/file-backed mappings are not all charged as private footprint.

The Linux fallback sums `/proc/PID/statm` resident pages, including shared pages
in each process, and excludes swapped-out pages. It is not the same metric and
has not been runtime-tested in this Apple Silicon task. Unsupported platforms
and accounting failures fail closed with `memory_monitor_failed`; they do not
silently disable the policy. An exited child is handled as a lifecycle event,
not an accounting failure.

The HTTP controller's own memory is outside the query budget. Query-count,
request-size, response-size, stack and execution limits still apply separately.
This policy does not monitor arbitrary descendants. The admitted Prolog policy
does not expose process creation; libcurl threads live inside the worker.

## Enforcement and limits

The supervisor samples at each event-loop iteration, with a maximum requested
poll wait of 50 ms, and checks before forwarding a completed page. While blocked
on output, it continues checking between writes/polls. Both active and idle
queries are monitored; background promises can allocate while a page is cached.

An observed excess triggers SIGKILL and waitpid before reporting
`memory_limit_exceeded`. The HTTP response is the ordinary error envelope:
`{"type":"error","data":"memory_limit_exceeded"}` or
`error(memory_limit_exceeded).` in Prolog format. The worker cannot catch this
external termination. The controller releases the query slot and source file.
A cached query terminated while idle is reclaimed when consumed, evicted or
expired; its worker is killed immediately on detection.

This is a sampled termination threshold, **not a hard allocation ceiling**.
Allocation can overshoot between samples; scheduler delay can increase detection
time, and short-lived peaks can be missed. A process may fail an allocation or
be killed by the OS before the supervisor reports a memory error. The configured
limit times the query count is therefore not a guaranteed node-wide maximum.
The separate node-wide budget below controls aggregate pressure with the same
sampled-enforcement limitations. Kernel-enforced containment remains future work.

A disconnected or stalled controller cannot be guaranteed an error event. If
output is already partial when a memory violation is detected, the supervisor
kills the worker and closes the stream; the HTTP layer discards incomplete
frames. Supervisor SIGKILL or an OS failure can still bypass normal cleanup.

## Validation

`memory_tests.py` uses disposable nodes, local C fixtures and a real Prolog
atom-interning workload that grows outside the fixed Prolog stacks. It checks:

- Active and idle allocation cause termination and worker reaping.
- Invalid limits are rejected and shared startup validation receives the budget.
- Injected accounting failure terminates the query instead of disabling limits.
- Repeated atom-memory exhaustion returns JSON and Prolog errors while two other
  clients complete paginated queries.
- Cached queries expire, sampled child processes disappear, and controller
  memory returns close to its warmed baseline (16 MiB allowance for allocator
  and thread caches, not an assertion of byte-for-byte equality).

`make test` runs a five-second mixed-load check. `make compiled-test` repeats it
against a compiled node bundle. The supervisor fixtures and real atom-growth
check also run with AddressSanitizer and UndefinedBehaviorSanitizer via:

```
make query-supervisor-asan
ISO_SUPERVISOR=./query-supervisor-asan python3 supervisor_tests.py
ISO_SUPERVISOR=./query-supervisor-asan python3 memory_tests.py
```

This instruments the selected standalone supervisor, not GNU Prolog or the HTTP
node's adjacent supervisor. The fixture's sampled peaks are observations and can
miss the true peak; the tests do not establish hours-long endurance or absence
of all leaks.

## Recorded Apple Silicon run

On macOS 26.5.1 (arm64), a paused ordinary query initially measured 950,584 bytes
for its supervisor and 4,997,624 bytes for its worker: about 5.7 MiB combined.
A 60-second run with a 24 MiB per-query budget then recorded:

| Measurement | Result |
|---|---:|
| Memory-limit terminations | 752 |
| Healthy answer pages | 29,486 |
| Slowest healthy two-page query | 48.9 ms |
| HTTP controller baseline / final footprint | 1,130,856 / 1,589,632 bytes |
| HTTP controller sampled peak | 1,884,544 bytes |
| Largest sampled worker + supervisor footprint | 30,344,032 bytes (28.9 MiB) |
| Retained query processes after recovery | 0 |

The observed overshoot illustrates why 24 MiB is a termination threshold, not a
hard ceiling. These are local workload measurements, not production capacity or
latency guarantees. The smoke and compiled-bundle checks additionally assert that
query source files and the node's temporary directory are removed.


## Node-wide budget and admission

`isobase-node --total-memory-mb N` sets a separate aggregate threshold, default
1024 MiB (1 GiB). The range is 1–1,048,576 MiB. It covers the controller, all
registered supervisors, and their worker children using the same platform metric
as the per-query limit. Both limits remain active. Requests cannot change either.

```
./isobase-node --memory-mb 256 --total-memory-mb 512 --max-queries 8
make total-memory-test
python3 memory_tests.py --total-memory-mb 96 --seconds 60
make isobase-node-asan
ISO_NODE=./isobase-node-asan python3 total_memory_tests.py
```

Before admission, the node charges each existing query the larger of its measured
usage and a minimum reservation of **16 MiB**, capped by the configured per-query
limit. A new query needs one additional reservation; resuming a retained query
does not. This protects against concurrent startup bursts before workers have
fully allocated their runtime. It is not a reservation for each query's entire
possible lifetime allocation. A configuration can therefore fit the controller
but have too little headroom to admit any queries.

If the admission charges exceed the total budget, the node evicts idle queries
in cache insertion order until the new request fits. A resumed continuation is
protected during this admission check and retains its original supervisor. If
only active/protected queries remain and there is insufficient headroom, the
request receives HTTP **503** with `total_memory_limit_exceeded`. Active work is
not stopped merely to create an admission reservation. These charges can reject
a request even when measured usage is still below the threshold.

Actual aggregate usage is checked by the main controller loop (50 ms poll wait),
before admission and before accepting a completed page. When it exceeds the
threshold, the controller first evicts oldest idle continuations. If that is
insufficient, it terminates the largest measured active query and remeasures,
repeating as necessary. Ties use registry order. The supervisor receives SIGTERM,
kills/reaps its worker, and is reaped by the controller. The active slot and its
pipe descriptors remain owned by the requesting thread until it handles the
termination; they cannot be reused underneath an in-flight request.

An interrupted active request receives HTTP **200** with the normal error body,
`{"type":"error","data":"total_memory_limit_exceeded"}`, or
`error(total_memory_limit_exceeded).` for Prolog format. A partial or completed
worker page is discarded if that query was selected for termination before its
response was accepted. Idle eviction retains the existing cache-miss behavior:
a later offset request restarts the goal and skips earlier answers.

The registry lock serializes admission, sampling, eviction and cancellation.
Shared-database startup validation uses the same registry and budget, before the
listener opens. Accounting failure closes admission with HTTP 503
`memory_monitor_failed`, releases idle queries and terminates active queries with
that error. When accounting recovers, new requests can proceed. If the controller
alone exceeds the budget, all queries can be reclaimed but admission remains
closed until usage falls; the controller itself is not killed.

`memory_tree.h` enumerates the supervisor's children and verifies parent ownership
before and after measuring each process. Exited/zombie children are ignored,
rather than being treated as accounting failures. The node samples registered
processes, not arbitrary descendants or workers orphaned by a supervisor crash.
The existing supervisor-SIGKILL cleanup limitation therefore still applies.
Sampling races, scheduler delay and allocation bursts allow overshoot; even the
aggregate budget is not a hard node-wide allocation ceiling.

## Aggregate-budget tests

`total_memory_tests.py` uses controlled allocation fixtures to check admission
reservations, JSON/Prolog 503 responses, insertion-order eviction, continuation
reuse and replay, active-query protection, largest-active termination after idle
eviction, growth while idle, startup validation, invalid limits, accounting-failure
recovery, and process/source cleanup. The fixture budgets account for measured
controller overhead so the same tests run under AddressSanitizer and
UndefinedBehaviorSanitizer. Production accounting has no fault-injection switch.

The real Prolog mixed-load mode uses larger interned atoms so it reaches the total
budget before GNU's separate atom-count ceiling. Two pressure clients run alongside
two paginating clients; 503 responses are checked and retried. It verifies forward
progress, bounded response time, expiry and recovery to the controller's warmed
baseline. Both the ordinary and compiled-bundle paths run this mode. These tests
remain bounded local workloads, not hours-long endurance guarantees.

### Recorded aggregate-pressure run

A separate 60-second Apple Silicon run used a 96 MiB node budget and a 256 MiB
per-query budget. It recorded 944 aggregate-memory terminations, 4,320 checked
HTTP 503 admission rejections and 13,294 healthy answer pages. The slowest
successful two-page query took 74.0 ms. Controller footprint went from 1,130,856
to 1,393,024 bytes, with a sampled peak of 1,999,232 bytes. No sampled query
processes or temporary source files remained after recovery.

The largest sampled aggregate was 133,466,200 bytes (127.3 MiB), demonstrating
overshoot beyond the configured 96 MiB threshold. These samples are not atomic
across processes and may also miss peaks. Healthy-page timing excludes rejected
attempts; the separate rejection count makes the admission cost visible.
