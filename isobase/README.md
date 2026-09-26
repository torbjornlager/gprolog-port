# GNU Prolog ISOBASE node

The target is an ISOBASE node compatible with the Trinity demonstrator.
[STATUS.md](STATUS.md) is the current contract/implementation/evidence index;
`CONFORMANCE.md` retains the historical audits and test methodology.
[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) consolidates the security and SWI
compatibility work, completion criteria and recommended order.
ISOTOPE is a possible later extension. The actor implementation and its
roadmap have been dropped; this project is focused on ISOBASE.

The shared contract and pinned comparison setup are documented in
[COMPARISON_BUILDS.md](COMPARISON_BUILDS.md).

The current deployment scope and release gates are in
[THREAT_MODEL.md](THREAT_MODEL.md): one trusted owner on loopback, with network
and untrusted-client deployments still unsupported.

## Run the development HTTP node

```
make
./isobase-node --auth open --port 8081 --max-queries 8 --time-ms 1000 --idle-ms 30000 --memory-mb 256 --total-memory-mb 1024
```

The server binds **127.0.0.1 only**. Port `0` requests an ephemeral port; the
first stdout line reports the chosen port as JSON. This is a local development
node with owner-token authentication and browser request checks. These examples
use explicit `--auth open` for trusted development only. Normal startup requires
`--auth-token-file FILE`; see [SECURITY.md](SECURITY.md) for setup and limitations.
Public deployment is not supported.

Outbound access is denied by default. Configure `--outbound-policy FILE` with
exact approved origins and IP pins; see [OUTBOUND_POLICY.md](OUTBOUND_POLICY.md).
This also applies to the RPC examples below. Redirects and ambient proxies are disabled.
For protected HTTPS peers, add an owner-scoped RPC credential rule as described
in [OUTBOUND_CREDENTIALS.md](OUTBOUND_CREDENTIALS.md).

```
curl --get http://127.0.0.1:8081/call \
  --data-urlencode 'goal=between(1,5,X)' --data 'limit=2'
curl --get http://127.0.0.1:8081/call \
  --data-urlencode 'goal=between(1,5,X)' --data 'offset=2' --data 'limit=2'
```

`GET /call` accepts `goal`, `template`, `src_text`, `format=json|prolog`,
`offset`, `limit`, `once=true|false`, and `timeout` in seconds. JSON responses
contain `type`, `data` binding objects and `more`; Prolog responses use
`success(Answers,More)`, `failure` and `error(Term)`. Goal/template variables
are parsed together. In JSON mode only named goal variables are returned;
explicit templates are used in Prolog mode. Free variables remain shared
within an answer and independent across separate Prolog answers.

A live continuation is cached by exact goal/template/source/format/once text
and next offset. A matching request resumes the existing supervisor and worker;
page size may change. On a cache miss the goal restarts and skips to the
requested offset, matching the demonstrator's documented cache-miss behavior.
`once=true` returns one page with `more:false` and releases the computation.
Submitted source is held in private temporary files for its query lifetime.

The maximum query count includes both running and cached queries. At capacity,
a new query evicts the oldest idle continuation when no free slot remains.
Resuming and recaching a continuation makes it newest, matching SWI's cache
insertion order. Eviction stops and reaps the supervisor and its worker and
removes request-local source files. Active queries are never evicted: if all
slots are running, new requests receive HTTP 503. A later request for an
evicted continuation restarts and skips to its offset, just like an expired
one. The default remains eight slots; `--max-queries` configures 1–32.
There are at most
32 client connections, with a 256 KiB request bound. An unused connection can
wait up to ten seconds for its first bytes, then closes silently. The two-second
header deadline starts with the first bytes, so browser preconnections do not
receive unsolicited HTTP errors. Partial headers time out with HTTP 408;
oversized headers receive HTTP 431. Each response has the supervisor's 1 MiB bound. Slow output is
bounded by a socket send timeout. The node reclaims expired continuations and
shuts down supervised workers on SIGINT/SIGTERM.

### Shared database

Supply an owner-managed Prolog file at startup:

```
./isobase-node --auth open --port 8081 --shared-db shared-example.pl
```

For example, `/call?goal=human(X)` then queries the provided sample without
`src_text`. `shared-example.pl` contains `human/1`, `list_price/2` and `price/2`.
In the ordinary build, no shared database is loaded when the option is omitted.
A compiled bundle embeds its shared database instead (see below).

The controller reads a regular text file of at most 1 MiB once, copies it to
its private temporary directory and validates that copy in a supervised worker
**before listening**. Invalid source or unsupported calls prevent startup.
Every query worker loads that same snapshot before loading request-local source.
Editing or removing the original file does not affect new queries or live
continuations. Restarting the node loads the updated file. Snapshot files are
removed during normal shutdown or failed startup.

Shared and local definitions have separate resolution contexts:

- A local clause can shadow a shared predicate for that request. Other requests
  continue seeing the shared definition.
- Calls inside a shared rule resolve against shared definitions, including
  calls through variables, `call/N`, higher-order predicates and DCGs. A local
  `list_price/2` therefore does not change how shared `price/2` computes prices.
- As in the demonstrator, declarations alone do not hide a shared predicate;
  actual local clauses are required. Empty declarations for otherwise unknown
  predicates still create an empty local predicate.
- `clause/2` exposes original local or shared application clauses. Local
  definitions shadow shared ones; shared callers retain shared resolution.
  Mutation and direct access to runtime internals remain blocked.

The ordinary build installs shared clauses in each worker's dynamic database.
Parsing memory is recovered after loading, while clauses remain alive until
worker exit. The optional compiled mode below keeps shared clauses in native
executable code. Both modes require shared code to fit the implemented ISOBASE
policy; the demonstrator's mixed actor examples are not a suitable shared file.

`shared_db_tests.py` checks shadowing, indirect calls, protected clauses,
snapshot stability, restart behavior and failed startup. Differential HTTP
tests also check shared/local resolution against the SWI demonstrator.

### Optional compiled shared database

Build a separate node bundle:

```sh
python3 build_shared.py shared-example.pl --output build/my-node
./build/my-node/isobase-node --auth open --port 8082
```

Use a new output directory for each build; the builder refuses to overwrite an
existing bundle. The normal `make` build and `--shared-db FILE` snapshot mode
remain available. A compiled node rejects `--shared-db` at startup, so it cannot
silently combine its embedded database with another snapshot.

The builder snapshots the input (regular file, no NUL, at most 1 MiB), runs the
same source validator and scope-preserving rewrite used by the runtime, then
compiles the rewritten clauses and public-to-private name mappings to native
code. The output includes the node, supervisor, worker, source snapshot,
generated Prolog/assembly and a manifest with source and implementation hashes.
It publishes the bundle only after a successful compile and worker smoke test.
The source and generated text files are not read by running workers.

Request-local definitions still use the ordinary private loader. They can shadow
shared names, but shared rules—including meta-calls, DCGs and timeout callbacks—
keep their shared resolution context. Mutation and direct
calls to internal names remain blocked. Source declarations are validated but
do not force shared predicates into dynamic storage: their supported semantics
are read-only. Empty declarations compile to an existing predicate that fails.

Workers now share clean executable pages through the OS instead of rebuilding
shared clauses on each query. Heaps, stacks, atom tables and any remaining runtime
data are still per worker. Database changes require a new bundle and node restart;
building another bundle does not change an existing node or its continuations.

The pinned GNU compiler needs two narrowly scoped build workarounds:

- On ARM64, some integer-switch comparisons use an invalid immediate. The builder
  replaces those generated `cmp x0,#constant` instructions with a load into the
  backend's scratch register and a register comparison.
- Integer switch keys can truncate to 32 bits, and switch sorting uses signed-int
  subtraction. First-argument integer constants outside ±1,000,000,000 therefore
  use an initial native unification helper instead of that index. Clause order,
  sharing and cuts are preserved, but those clauses may have slower lookup.

Neither workaround modifies the installed GNU compiler or its source checkout.
The manifest records the number of ARM64 instruction fixes. Regression tests
cover index boundaries, wide signed keys, source rejection, local overrides,
protected shared calls, immutable build inputs and native-node RPC.

```sh
make compiled-test
ISO_NODE=./build/my-node/isobase-node python3 http_tests.py
ISO_NODE=./build/my-node/isobase-node python3 eviction_tests.py
```

`compiled_benchmark.py` builds a 10,000-fact catalogue and compares fresh HTTP
query latency and memory at 8, 16 and 32 retained queries. It records both summed
RSS and macOS `footprint` totals. Footprint measures charged/dirty memory and
excludes clean file-backed executable pages; neither number alone is a complete
measure of unique physical RAM. The benchmark is optional and is not a test.

A run on this Mac with 10,000 facts (427,788 bytes of source) measured:

| Retained queries | Snapshot footprint | Compiled footprint |
|---:|---:|---:|
| 8 | 122.9 MiB | 45.8 MiB |
| 16 | 244.6 MiB | 90.3 MiB |
| 32 | 487.7 MiB | 179.6 MiB |

These are macOS footprint totals, not summed RSS, and exclude clean file-backed
code. Fresh-query median latency was about 49–53 ms for snapshot mode and
8–9 ms for compiled mode (12 requests per configuration, including worker
startup and HTTP). The native executable was about 12.6 MiB versus 1.1 MiB for
the ordinary worker. Actual benefits depend on source size, code and workload.
Raw results: `build/benchmark-1789284745513753000/results.json`.

### RPC and promises

`rpc/2-3`, `promise/3-4`, `yield/2-3` and `promise_cleanup/1` are now
implemented. `rpc` unifies remote answers with the caller's goal and fetches
subsequent pages on backtracking. `promise` starts one HTTP request and returns
an integer reference immediately; `yield` receives its `success(Answers,More)`,
`failure` or `error(Term)` message. Several promises can run concurrently.

For example, on the development node (calling itself through HTTP):

```prolog
rpc('http://127.0.0.1:8081', member(X,[a,b,c]), [limit(1)])

promise('http://127.0.0.1:8081', member(X,[a,b,c]), R,
        [template(X),limit(2)]),
yield(R, Message)
```

URI arguments accept HTTP(S) atoms or `Host:Port`. Options include `limit`,
`once`, remote `timeout`, transport `http_timeout`, and source options
`src_text`, `src_list`, `src_predicates` and HTTP(S) `src_uri`. Sources are
combined in option order. `src_predicates` exports only explicitly listed
request-local predicates using their original clauses; include dependencies
explicitly. Export via `src_predicates` remains local-only; shared clauses can be inspected with `clause/2`. Promises
also accept `template` (default: the goal) and `offset` (default: zero).
As in the demonstrator, RPC chooses its own variable template and starts at
zero; `once(true)` means one page, not one answer.

`yield(R,M,[timeout(Seconds),on_timeout(Goal)])` retains the promise after a
wait timeout and executes `Goal` through the caller's execution policy. The
callback defaults to `true`. A later yield can still receive the response.
`yield/2` waits for a matching message, as in the demonstrator. A pattern
that cannot match the single response will wait until the query is terminated.
`yield/3` consumes the response before unifying it with `M`; use a fresh
variable then inspect the message. Unknown references fail in
`yield/2` and invoke the timeout callback in `yield/3`.

`transport.c` uses libcurl and a bounded pool of network threads. These threads
never call the GNU Prolog runtime. A worker owns at most 16 outstanding promises,
each with a 1 MiB response bound and 256 KiB URL bound. Completion or explicit
cleanup joins the thread and frees its slot and buffers. Query exit/termination
releases all remaining transport resources with the worker process. References
are valid only inside that query lifetime, including its live continuations;
they cannot be handed to an unrelated `/call` request.

Current transport limits/differences:

- Outgoing page size uses the demonstrator's default of 10,000,000,000. The
  node accepts sizes up to that value without allocating by answer count;
  the response byte bound and execution deadline remain authoritative. Use
  a smaller explicit limit for incremental answers. RPC walks pages unless
  cut or `once(true)` is requested.
- HTTP timeout defaults to 30 seconds, with explicit timeouts bounded to
  0–300 seconds (zero transport timeout becomes 1 ms). The owning supervisor's
  cumulative execution budget still applies, including network waits.
- Only explicitly approved HTTP(S) destinations are supported; redirects are denied. Owner-scoped
  HTTPS bearer credentials are supported; caller-supplied authentication options,
  relative source URIs and arbitrary SWI `http_open` options remain unavailable.
  HTTPS verification remains enabled.
- Transport failures throw catchable diagnostic errors on RPC/yield. The SWI
  promise implementation can instead log a transport failure and leave yield
  waiting. Remote Prolog errors remain `error(Term)` promise messages.
- Cleanup cancels the local HTTP request. It does not issue a remote continuation
  deletion request; unused remote continuations expire under the remote node's
  normal idle policy. Cancellation can wait for libcurl to observe its cancel
  flag; the supervisor remains the hard termination boundary.

Builds now link libcurl and pthreads (available in the macOS development SDK).
`make rpc-test` launches temporary GNU and SWI nodes and tests all three call
directions, pagination, bindings, source transfer, overlapping promises, timeout
retry, cleanup, malformed/oversized responses and policy enforcement. It uses
`TRINITY_ROOT` if set, like `make diff-test`. Earlier runs also covered the
worker C code with AddressSanitizer and UndefinedBehaviorSanitizer. The current
RPC suite stops at the known zero-limit disagreement; later cases are not
validated by that failing run:

```sh
make query-worker-asan
ISO_WORKER=./query-worker-asan python3 rpc_tests.py
```

This instruments the worker and transport C code; the GNU Prolog runtime and
Prolog-generated machine code are not instrumented.

### Compatibility status

The initial HTTP path is implemented, but this is **not full ISOBASE
conformance**. Current limits and known differences include:

- HTTP default page size is 10,000,000,000, matching the demonstrator.
  Zero-sized fresh queries fail without executing the goal; on a live
  continuation zero selects the default page size in GNU. This is not current
  SWI agreement: zero-limit validation remains the open D01/K01 decision.
  Response byte and execution bounds apply regardless of page size.
- The node owner sets the cumulative execution budget. Request `timeout` can
  tighten the wait budget but cannot increase the owner's limit.
- Error envelopes use `type:error` and `data`, but error strings are currently
  diagnostic terms rather than all of the demonstrator's friendly messages.
- JSON variable filtering follows the demonstrator's anonymous-helper visibility
  rules for the tested ASCII variable names. Cache keys use exact text rather than
  normalized Prolog variants. Prolog answers use standard quoted term syntax;
  operator spelling may differ from the demonstrator's canonical writer.
- Remaining edge-case conformance checks,
  multi-user authorization and hard OS memory containment remain unfinished.
  Owner-token authentication and browser request checks are implemented; see SECURITY.md.

Validation: `make test` includes the worker, source, policy, supervisor and HTTP
suites, including eviction order, process cleanup and active-query protection. `make diff-test` launches temporary GNU and SWI nodes and compares 42
supported `/call` cases with the Trinity demonstrator, including paging,
variable sharing, source and both formats. It uses `TRINITY_ROOT` when set.
HTTP tests also run with the C server instrumented for address/undefined behavior:

```
make isobase-node-asan
ISO_NODE=./isobase-node-asan python3 http_tests.py
```

## Implemented: source loading, execution policy and private query worker

`worker.c` drives a recoverable GNU Prolog query, retaining its choice points
between answer pages. Optional source is loaded into that worker before its
query begins. Goal and template are read together, preserving variable
sharing. Each answer is serialized before backtracking. The worker recovers
the query on exhaustion, error, cancellation or control-pipe EOF, then exits.

```
make test
./query-worker 'query(between(1,5,X),X)' 2
```

The first page is emitted immediately. Send `next` followed by a newline for
each further page, or `stop` to cancel. This is a **private test protocol**:
its JSON contains canonical Prolog answer strings and is not the demonstrator's
public JSON binding format. This is a local development executable with an
initial language policy, not a complete sandbox or public execution service.
Submitted source can be supplied using a controller-owned local file:

```
./query-worker 'query(colour(X),X)' 2 --source example.pl
```

`source.pl` reads and validates source before installing its clauses in the
worker's dynamic database. It supports facts, rules, recursion, cuts, DCGs,
and `dynamic`, `multifile` and `discontiguous` declarations (including empty
predicates). These clauses use GNU Prolog's dynamic execution path; they are
not compiled to native code per request. Temporary parsing/expansion terms
are recovered before the application query begins. The worker process owns
all submitted predicates and releases them when it exits.

The loader rejects arbitrary directives, initialization, custom operators,
expansion hooks, reserved worker names and redefinition of existing predicates.
Source files must be regular files no larger than 1 MiB. The file argument
is a controller-owned path, not a public request parameter.
The HTTP controller translates `src_text` into its own private input file.

Additional native application predicates can be compiled using
`make -B APP=app.pl`. Such predicates are not automatically admitted by
the execution policy; exposing them requires an explicit policy decision.

### Execution policy

`policy.pl` admits guarded RPC/promise operations, an explicit set of pure built-ins and predicates defined
in submitted source. It rewrites source bodies before installing executable
clauses and rewrites the query before running it. Native conjunction,
disjunction, if-then-else and cut remain in place to retain control semantics.
Variable goals and `call/1-8` are checked at invocation. Guarded wrappers cover
`maplist/2-5`, `foldl/4-7`, `phrase/2-3`, `bagof/3` and `setof/3`; nested goals
in `findall/3`, `once/1`, negation and `catch/3` are checked too.

`clause/2` accesses submitted and shared application predicates and returns their original
bodies, without inserted guards. Runtime predicates, module qualification,
database mutation, general I/O, process control and loading predicates are
not admitted. Unknown predicates produce a policy error. Uninstantiated
meta-calls produce an instantiation error. Cyclic answer templates are rejected
before canonical serialization.

This is a **partial ISOBASE implementation**, not a complete conformance claim.
The listed core prologue predicates are implemented; exhaustive mode/error
conformance remains to be established. See `CONFORMANCE.md` for the ledger. Statically visible forbidden calls in source are rejected even
in unused clauses; dynamically constructed calls are checked before execution.
The regression tests establish specific cases, not a security proof. The supervisor below provides active/idle deadlines, stack and response
bounds and a sampled combined worker/supervisor memory budget; the HTTP controller
adds node-wide concurrency and memory admission, with idle-first reclamation and
largest-active termination under aggregate pressure. See MEMORY_LIMITS.md for limits.

The worker evaluates one answer ahead to detect exhaustion. If that evaluation
throws, it preserves the already obtained page and reports the exception on
the next continuation request. `more:true` therefore means a continuation
event remains, which may be an exception. The same continuation behavior is exposed through `/call`. Lookahead may run
arbitrarily long in a bare worker; the supervisor enforces the execution budget.

Policy tests cover permitted control flow and higher-order calls, cut scope,
source introspection and direct/indirect denied operations. Source tests cover recursive and nondeterministic programs, declaration
semantics, grammar expansion, failure/exception propagation, definition
protection, rejected directives, syntax errors, source isolation and the file
size limit. Worker tests cover paging, shared variables, cuts, success/failure, immediate and
deferred exceptions, cancellation, EOF, syntax errors, JSON escaping and
1,000 repeated allocation-heavy recoverable queries. In the tested GNU Prolog
build, global-stack usage before and after those 1,000 queries was 4,216 bytes.
This measures temporary heap recovery, not RSS, atom-table reclamation or
unbounded single-query execution. A fresh worker per query lifetime will also
release source, interned atoms and other runtime allocations on process exit.

## Implemented: per-query C supervisor

`query-supervisor` launches the adjacent `query-worker`, owns its pipes and
reaps it when the query finishes, fails, is cancelled or expires. It uses the
same private page protocol and retains the worker between continuation requests.
Each supervisor owns one query lifetime; the HTTP server coordinates multiple supervisors.

```
./query-supervisor 'query(between(1,5,X),X)' 2 --time-ms 1000 --idle-ms 30000
./query-supervisor 'query(colour(X),X)' 2 --source example.pl
```

Keep stdin open while awaiting a response. Send `next` only after a page with
`more:true`; send `stop` at any point to cancel. Closing stdin abandons the
query. Invalid commands terminate that lifetime with a protocol error.

| Option | Default | Meaning |
|---|---:|---|
| `--time-ms` | 1000 | Cumulative elapsed active time across source loading and all pages; idle waiting is excluded |
| `--idle-ms` | 30000 | Time allowed to request the next page; partial commands do not extend it |
| `--heap-kb` | 16384 | GNU Prolog global-stack allocation in KiB |
| `--memory-mb` | 256 | Combined worker and supervisor memory budget in MiB, sampled during execution and idle waiting; also available on the HTTP node |
| `--max-output` | 1048576 | Maximum bytes in one complete worker response, including newline |

The supervisor also sets local/trail/constraint stacks to 8192/4096/4096 KiB
and disables core dumps. These are stack limits, **not a total RSS or dynamic
allocation limit**. A too-small stack may cause GNU Prolog to terminate or
emit a diagnostic; this is reported as a worker failure, not a guaranteed
structured stack-overflow exception. The HTTP controller supplies concurrency
and aggregate memory admission (`--total-memory-mb`, default 1024 MiB).
The separate per-query memory budget covers process allocations using macOS
physical footprint (Linux fallback: RSS); it can overshoot between samples.
See [MEMORY_LIMITS.md](MEMORY_LIMITS.md) for scope, measurements and tests.

Only complete worker response lines are forwarded. Time/output-limit failures
replace an unfinished page with one error event rather than forwarding partial
JSON. Error terms include `time_limit_exceeded`, `continuation_expired`,
`output_limit_exceeded`, `memory_limit_exceeded`, `memory_monitor_failed`,
`cancelled`, `controller_disconnected`, `worker_exit`
and `worker_protocol_error`. Supervisor output backpressure is bounded to one
second; a disconnected or non-reading controller cannot be guaranteed a final
event. SIGINT/SIGTERM trigger worker cleanup. An uncatchable supervisor SIGKILL
is not covered by that cleanup guarantee; stronger OS containment is future work.

Supervisor tests exercise live paging, cumulative active budgets, idle expiry,
non-cooperating computations, cancellation, EOF, source forwarding, output and
heap exhaustion, worker death, signal cleanup, and two independent queries.
The supervisor tests also pass with AddressSanitizer and UndefinedBehaviorSanitizer:

```
make query-supervisor-asan
ISO_SUPERVISOR=./query-supervisor-asan python3 supervisor_tests.py
```

The test harness uses `ps` to verify that workers were reaped. Only the C
supervisor is instrumented by this target; GNU Prolog itself is not.

## Work remaining for an ISOBASE node

1. Complete the mode/error and portability audit recorded in `CONFORMANCE.md`.
2. Close the documented HTTP/source compatibility gaps and expand differential
   testing to the full intended profile contract.
3. Complete isolated-deployment network controls, public execution controls and hard OS memory containment
   beyond the sampled query and node budgets.
4. Extend endurance and failure testing across concurrent requests, continuation
   expiry and resource exhaustion before claiming full ISOBASE conformance.

Contract references in `/Users/lager/trinity-demonstrator/`:
`docs/WEB_PROLOG_BUILTINS_ACCEPTANCE_MATRIX.md`, `docs/ARCHITECTURE.md`,
`prolog/web_prolog/node_call_context.pl`, `node_engine.pl`, and
`node_response.pl`. Some older profile-matrix text differs from newer endpoint
documentation; resolve details against the demonstrator and its tests.

## Possible ISOTOPE extension

A session worker could recover each completed/stopped query while preserving
its dynamic database. It must retain a still-active query across answer pages
and input waits. Correct abort/recovery, session I/O and source isolation need
separate validation. Neither profile eliminates heap exhaustion within an
individual allocating computation; GNU Prolog still has no general heap GC.


## Historical implementation and audit notes

The following sections describe successive audit batches. Their case counts and
pass claims apply to those batches, not the current complete suite; see STATUS.md.

### Shared-clause inspection and proof trees

Example 18 now runs against genuine shared databases: only `prove/2` is
shipped between nodes. `make test` checks the interpreted path;
`make compiled-test` checks two separately compiled shared databases and the
complete proof terms for Socrates, Plato and Aristotle. The `@` proof annotation
operator is available when reading goals and source.

Compiled bundles include original clauses as native `iso_native_clause/2`
metadata, as well as executable code. Workers do not assert a dynamic copy of
this metadata at startup. This increases the binary size; the earlier memory
and latency measurements predate this addition and have not been remeasured.
Rebuild existing bundles to enable shared inspection.


### Relational-mode compatibility

The conformance suite now includes every supported `call`, `maplist` and
`foldl` arity, plus selected relational modes and DCG controls (196 samples
in total). Open lists can be generated on backtracking, e.g.
`maplist(=(a),L)` yields `[]`, `[a]`, `[a,a]`, and so on. Use a finite page
limit for unbounded generators. Scalar `phrase/3` list arguments raise
catchable type errors. See `CONFORMANCE.md` for coverage limits and the
separately tested compound-DCG discrepancy in the SWI node.


### Text and numeric portability

Unicode atom operations now use code points and preserve UTF-8 through HTTP,
RPC and compiled shared source. Quote non-ASCII atoms. GNU retains bounded
integers and code-list double-quoted literals; SWI strings and bignums remain
compatibility gaps. See [TEXT_NUMERIC_BOUNDARY.md](TEXT_NUMERIC_BOUNDARY.md)
for the precise range, examples, test accounting and remaining limitations.


### RPC compatibility audit

Unicode `src_text` character/code lists and approved HTTP(S) source are
supported. Redirects are denied by the owner-controlled outbound policy. Promise
state and error cleanup tests now cover both calling runtimes where the public
APIs overlap. See [RPC_BOUNDARY.md](RPC_BOUNDARY.md) for tested behavior, cyclic
exception guards and remaining host differences.


### HTTPS trust and source deadlines

Peer certificates and hostnames are verified. Node owners may set `ISO_CA_FILE`
to an absolute CA-bundle path before starting the node; callers cannot change
trust through query options. `http_timeout` applies to each `src_uri` download
as well as RPC transport. Certificate, CA-file and handshake failures have
distinct catchable GNU diagnostics. See [RPC_BOUNDARY.md](RPC_BOUNDARY.md) for
the 17 local HTTPS checks and precise deadline/trust limitations.


### Predicate-level audit

[PREDICATE_CHECKLIST.md](PREDICATE_CHECKLIST.md) lists the 97 required callable
predicate/arities, implementation locations, evidence entry points and remaining
audit work. Its first 58-case batch corrected 18 text/list discrepancies; the
corpus then had 311 passing cases with host boundaries counted separately.
No predicate is marked fully conformant solely because its samples pass.


The second predicate audit adds 114 character/number conversion checks. Input
list coercion, partial output modes, selected error precedence and decimal
exponent parsing now match the sampled SWI behavior; overflowing float text is
rejected. The corpus then had 425 cases.

The third predicate audit adds 148 list and integer-relation checks, bringing that
corpus to 573 cases. Remainder modes, improper lists and bounded cyclic-list access
match the sampled SWI behavior. `succ/2` argument handling and `between/3` infinite
upper bounds are corrected. Infinite enumeration remains limited to GNU integers;
cyclic error culprits use finite representation errors. See the predicate checklist
for remaining numeric, term and higher-order audits.


The fourth audit adds 236 numeric lexical, formatting and round-trip cases.
Leading plus signs, integer separators and radix forms now work in the sampled
number conversions. Float output uses a shorter spelling that preserves its
binary value when read back. The corpus at that stage had 809 cases, including 23 explicit
host boundaries rather than SWI matches. Source syntax remains GNU's; bignums,
rationals, non-finite spellings and Unicode numeric syntax remain documented gaps.


The fifth audit adds 174 term and all-solutions checks. Output-list mismatches,
selected error precedence and exception timing now follow the sampled SWI
behavior. Variable sharing, sorting and grouped solutions are checked in ordinary
queries and compiled shared clauses. The corpus has 983 cases, including 23
explicit host boundaries. Full rational-tree semantics and exhaustive determinism
remain open; the next checklist batch covers remaining DCG constructs and modes.


The sixth audit adds 75 DCG checks, bringing the corpus to 1058 cases. GNU now
handles `{}` in grammars and the sampled invalid terminal-list errors. The SWI
demonstrator's grammar-closure guard was also corrected; source changes are tested
on disposable nodes, without restarting a running SWI deployment. Forbidden
embedded goals remain guarded. The checklist records the remaining DCG contexts.


The seventh audit adds 100 higher-order, arithmetic and template-precedence
checks, bringing the corpus to 1158 cases. It corrects sampled arithmetic order,
rounding and zero cases, and keeps conjunction templates inside one answer-list
element. The 23 explicit host boundaries remain. Source and RPC option modes are
next in the checklist.


The eighth audit adds 61 source/RPC option cases, bringing the corpus to 1219
cases with 25 explicit host boundaries. GNU omits an unbound remote timeout
without binding it and matches sampled once-option behavior. Source composition
preserves option order; the corresponding SWI accumulator bug was fixed in source
and tested on disposable nodes. GNU's stricter negative-timeout policy remains.


The ninth audit adds 58 RPC URI and validation-order cases, bringing the corpus
to 1277 cases with 42 explicit host boundaries. Source downloads preserve exact
URLs, remote timeouts are validated before source composition, and HTTP timeout
validation follows the sampled mode/error contract. Eleven separate checks cover
ordered source failures and transport-slot recovery, including compiled workers.
See RPC_BOUNDARY.md for the URI and transport differences that remain.


The node now also enforces a sampled aggregate memory budget via
`--total-memory-mb` (default 1024 MiB), including controller overhead. Admission
uses a minimum 16 MiB query reservation, evicts idle continuations first and
returns HTTP 503 when no room remains. Actual excess triggers idle-first
reclamation followed by largest-active termination. See MEMORY_LIMITS.md for
error semantics, startup validation, measurements and overshoot limitations.
