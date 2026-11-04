# Pinned comparison builds

C01 provides a versioned draft shared contract and reproducible comparison input
selection. SWI is a peer implementation, not the gold standard. See
[contract governance](contracts/README.md) and [version 0.2.0](contracts/0.2.0/CONTRACT.md).

## Locked inputs

`comparison-lock.json` pins:

- Trinity source `f237dd5c806893dad17c95cad9a2dc1692a73607`.
- GNU Prolog source `5976ac516c9fbd1d740d41b238597e327302baea`.
- SWI-Prolog 10.1.3 and GNU Prolog 1.6.0 runtime versions.
- The measured Apple Silicon Darwin environment, Apple Clang version, libcurl
  configuration/runtime version strings and observed SWI/GNU/compiler executable
  SHA-256 hashes. These identify the baseline installed builds.
- Integrity hashes for every file in the versioned contract directory.

The current baseline supports reproduction on the recorded Apple Silicon macOS
environment. Other operating systems are not thereby validated. Pin verification
checks clean source revisions and runtime versions before launching nodes;
default comparison harnesses also require the recorded environment and runtime
binary fingerprints. It refuses source changes and untracked files in either
comparison checkout. It never resets or changes those checkouts automatically.

These checks identify inputs, not a hermetic build proof. The installed runtime
could depend on other libraries, and a source revision plus version string does
not prove the binary was built from that source. Release-grade reproducible
packaging, dependency integrity and the full platform matrix remain S15/V06/V07.
Per-run binary/source fingerprints make local changes visible rather than
mislabel them as the repository's HEAD. OS patching or a rebuilt executable can
require a reviewed baseline refresh even if behavior has not changed.

## Fresh-checkout setup

Read the exact revisions from the lock rather than tracking a branch tip:

```sh
# From the gprolog-port root; directories must not already exist.
git clone https://github.com/didoudiaz/gprolog.git gprolog
git -C gprolog checkout --detach 5976ac516c9fbd1d740d41b238597e327302baea
git clone https://github.com/torbjornlager/trinity-demonstrator.git ../trinity-demonstrator
git -C ../trinity-demonstrator checkout --detach f237dd5c806893dad17c95cad9a2dc1692a73607
```

Build GNU using the root README's pinned configure/build/install instructions.
Install SWI 10.1.3 and the recorded toolchain for baseline comparison. The lock
contains local binary fingerprints, not redistributable runtime installers; if a
fresh build differs, the tool reports the mismatch instead of claiming exact
reproduction. Use exploratory preflight to collect its provenance for review;
accept a new baseline only after the environment/build differences are understood.
Use explicit `COMPARISON_MODE=source-pinned` to run the same harnesses on a fresh
build whose fingerprints differ (for example due to installation paths). This
still rejects dirty/wrong source revisions and runtime versions, labels the run
separately and records its actual builds; it does not establish baseline identity
or validate a new supported platform.

Paths are configurable and do not contain developer home directories:

| Setting | Default | Purpose |
|---|---|---|
| `TRINITY_ROOT` | sibling `../trinity-demonstrator` | Clean pinned SWI node checkout |
| `GPROLOG_SOURCE` | project `gprolog/` | Clean pinned GNU source checkout |
| `SWIPL` | `swipl` on PATH | SWI runtime executable |
| `GPROLOG` | project `install/bin/gprolog` | GNU runtime executable |
| `COMPARISON_MODE` | `baseline` | `source-pinned` explicitly permits other builds, retaining revision/version checks |
| `CC` | `cc` on PATH | Compiler executable, not a command with flags |
| `CURL_CONFIG` | `curl-config` on PATH | libcurl build version probe |

For example, set `SWIPL=/Applications/SWI-Prolog.app/Contents/MacOS/swipl` if the
macOS application executable is not on PATH. `TRINITY_ROOT` works for conformance,
differential, RPC and latency harnesses. Local predicate inventory and proof-tree
fixtures use versioned snapshots and need no Trinity checkout.

```sh
make -C isobase comparison-check  # Strict baseline check and provenance
make -C isobase contract-test     # Pinning regressions and both nodes vs explicit expectations
make -C isobase conformance-test  # Includes contract-test, then broader comparisons
make -C isobase rpc-test
# Read-only diagnosis of another environment; not exact baseline evidence:
python3 isobase/comparison_config.py --exploratory
# Same source/version pins from another installation path or build:
COMPARISON_MODE=source-pinned make -C isobase contract-test
```

Each preflight/harness run creates a distinct ignored directory under
`isobase/build/comparison-runs/`, containing `provenance.json`. It records the
contract/lock, checked revisions, implementation HEAD and dirty status, source
and executable hashes, platform, Python and toolchain observations. Contract and
conformance runs also place their results beside that provenance. Preserve the
printed directory when sharing results. There are no tokens or process environment
dumps in these reports. Absolute local paths and dirty filenames are recorded.

The known zero-limit mismatch remains a failure in the broader suites. C01 does
not resolve K01 or redefine a mismatch as compliance. Always report independent
contract assertions, differential agreement and deliberate boundaries separately.

## Updating pins

Review source revision/version changes and their rationale. Verify checkout
cleanliness, record the intended toolchain/runtime fingerprints, and update the
lock deliberately; there is no automatic “bless this machine” command. Run the
independent contract tests and all affected comparisons and retain provenance.
A semantics change requires a new contract version and decision rationale,
regardless of whether it first appears in GNU or SWI. Do not silently edit an old
version or turn a comparison implementation into the specification.

## C04 independent requirements

`make boundary-contract-test` runs 29 required boundary probes plus ten scoped
[TU Wien cases](ISO_TEST_SELECTION.md) on each pinned node. It currently fails
on known unmet requirements; those failures are not waived. Runtime/source pins
are unchanged. The broad comparison suite leaves 42 classified observations
unscored, rather than counting GNU-specific expected outcomes as conformance.

Comparison fixtures now create owner-only temporary outbound policies and grant
only their exact dynamically allocated origins. `outbound_test_policy.py` shares
these grants with test child processes; it never edits an owner-supplied policy.
Missing policy remains deny-by-default in production and direct workers.

## Current-source candidate comparisons

The historical baseline and source-pinned modes retain their original locks.
Use an explicit candidate selection to compare a newer demonstrator and SWI:

```sh
COMPARISON_MODE=candidate \
COMPARISON_TRINITY_REVISION=FULL_40_CHARACTER_DEMONSTRATOR_HEAD \
COMPARISON_SWI_VERSION=10.1.19 \
WP_NATIVE_STATE=/path/to/validated/native-swi.json \
python3 conformance_tests.py
```

Candidate mode still checks the selected HEAD, explicit SWI version, GNU engine
source pin and contract hashes. It records dirty status and hashes of every
tracked nonsymlink demonstrator input as well as GNU sources and binaries.
This is current candidate evidence, not a reproduction of the historical build.

## Current manual versus the retained ISO draft

The demonstrator's current language manual governs new deployment checks. The
older ISOBASE 0.2 draft remains an independently versioned target: its required
code-list reader mode, ISO arithmetic restrictions and closed transport options
must not silently override the current manual's selected reader modes and
explicit native transport options. Its existing required failures and frozen
locks remain intact as historical draft evidence.

Use the implementation-neutral current-manual selection for release checks:

```sh
python3 ../../trinity-conformance/adapters/local_isobase.py \
  --demonstrator-root ../../trinity-demonstrator --gnu-root .. \
  --output /fresh/path/current-manual
python3 ../../trinity-conformance/runner/validate_reports.py /fresh/path/current-manual
```

It starts disposable, bounded SWI and GNU nodes and runs the shared ISOBASE HTTP
and HTTP interoperability manifests unchanged, with exact fixture-only egress
grants. Every selected required assertion must pass; missing reports, process
errors and unsupported cases fail the selection. It does not claim full ISOBASE
certification or count differences in the old draft as passes.

`conformance_tests.py --family NAME --report FILE` can reproduce a selected older
comparison family without replacing historical evidence. `--trace-peer` records
its disposable peer's HTTP responses for fixture/admission diagnosis. Those
comparisons keep their original assertions and nonzero status on disagreement.

The current-manual candidate now rejects `template/1` and `offset/1` on
`rpc/3`, requires positive page sizes and validates every scalar/source
occurrence before fetching or dispatching. `yield/3` checks all timeout and
callback values before collection, preserving the promise after invalid options.
The 55-assertion option fixture checks rejection without peer requests, duplicate
validation, first-setting precedence, source-before-I/O and promise retry. These
are runtime fixes against the current manual, independent of the retained draft.
