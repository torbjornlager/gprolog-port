# GNU Prolog ISOBASE node project

Created 2026-09-12, independently of the Trinity demonstrator.

## Current target: ISOBASE

The immediate target is now an **ISOBASE node**, with ISOTOPE a possible
later extension. The actor implementation and its roadmap have been dropped.
GNU Prolog's lack of general heap GC makes explicit query completion/recovery
boundaries a better fit than arbitrary long-lived actor goals.

[isobase/README.md](isobase/README.md) records the implementation and remaining
work. The project now has a loopback C HTTP server for `/call`, with submitted
source, JSON bindings, Prolog-text responses, live pagination and query admission
limits. C supervisors enforce execution/idle deadlines, stack and response
bounds, a sampled combined worker/supervisor memory budget, and worker cleanup.
Memory budgets default to 256 MiB per query and 1 GiB across the node, with
admission checks and idle-first reclamation; see
[MEMORY_LIMITS.md](isobase/MEMORY_LIMITS.md) for its scope and overshoot limitations. The source and execution policy checks direct and
indirect calls. An owner-supplied `--shared-db FILE` is snapshotted and
validated at startup. Request-local overrides remain separate from shared rules,
and continuations retain the startup database until the node restarts.

RPC, promises and yield now work over HTTP(S), including source transfer and
pagination. Bounded libcurl threads perform network I/O without entering the
Prolog runtime. Promise references and resources belong to one query worker.
`make rpc-test` checks GNU→GNU, GNU→SWI and SWI→GNU interoperability, timeouts,
cleanup and policy enforcement. Transport limits and compatibility differences
are documented in the ISOBASE README.

An optional `isobase/build_shared.py` build embeds validated, rewritten shared
predicates and their name mappings as native code in a separate node bundle.
Request-local source remains private and interpreted. The ordinary snapshot
mode remains available; native bundles cannot be overlaid with another snapshot.
See the ISOBASE README for build instructions, measurements and the isolated
workarounds for integer indexing in the pinned GNU compiler.

All current suites pass, including 42 differential HTTP cases against the SWI
Trinity demonstrator. The 1,000-query recovery test still returns to the same
heap baseline. This is an initial ISOBASE HTTP implementation; remaining profile
facilities, authentication and documented compatibility gaps are not complete.

```sh
cd /Users/lager/gprolog-port/isobase
make test
./isobase-node --port 8081
```

## Initial C-interface experiment

A C controller successfully drives two independent GNU Prolog computations
using one OS process per computation. Both pause *inside* a foreign C
predicate, with live Prolog bindings and choice points. The parent resumes
them in the non-nested order A1, B1, A2, B2. Binding identity, backtracking,
cut and subsequent exception delivery are checked.

The separate single-runtime experiment confirms nested query behavior:
A1, B1, B2, close B, A2. The public query API does not expose an independently
selectable engine/context handle. These experiments support the use of
independent process workers for concurrent ISOBASE query lifetimes.

## Building from a fresh clone

The upstream GNU Prolog checkout, private installation, generated bundles and
logs are local build products and are intentionally excluded from this repository.
`gprolog/` is a separate checkout, not a submodule. Keep it at the pinned revision.

From this repository's root (with Git, a C toolchain, make and libcurl development
files available):

```sh
git clone https://github.com/didoudiaz/gprolog.git gprolog
git -C gprolog checkout --detach 5976ac516c9fbd1d740d41b238597e327302baea
project_root="$PWD"
cd gprolog/src
./configure --with-install-dir="$project_root/install" \
  --without-links-dir --without-doc-dir --without-html-dir --without-examples-dir
make
make install
make check
cd "$project_root"
make -C isobase all
```

The current implementation is tested on Apple Silicon macOS. The commands above
rebuild the private runtime; they are not a claim of portability to every platform.
Python 3 is needed for the test scripts, and differential tests additionally need
SWI-Prolog and the Trinity demonstrator checkout. Some test paths still refer to
the original developer workspace. Historical build logs, benchmark bundles and
test-result files referenced below remain available locally but are not published.

## Installation and validation

- Official source: https://github.com/didoudiaz/gprolog
- Pinned checkout: `5976ac516c9fbd1d740d41b238597e327302baea`
- Source version: GNU Prolog 1.6.0 (Git checkout, not a release tarball)
- Native target: aarch64-apple-darwin25.5.0
- C compiler: Apple's `/usr/bin/gcc` (Clang)
- Private installation: `install/`; no system installation or PATH changes
- Upstream `make check`: all tests succeeded, including native instruction
  checks and compiler/built-in bootstrap checks; see `check.log`
- Embedding experiment: 40 passing runs; see `experiment/results.json`
- Downloaded GNU Prolog tracked source remains unmodified

Directories:

| Path | Contents |
|---|---|
| `gprolog/` | Official source checkout and build products |
| `install/` | Private binaries, headers and libraries |
| `isobase/` | C query worker, lifecycle tests and ISOBASE implementation plan |
| `experiment/` | C controller, Prolog program, Makefile, test driver, results |
| `build.log`, `install.log`, `check.log` | Build and upstream validation output |

Re-run the experiment:

```sh
cd /Users/lager/gprolog-port/experiment
make test
```

Build configuration, for reference:

```sh
cd /Users/lager/gprolog-port/gprolog/src
./configure --with-install-dir=/Users/lager/gprolog-port/install \
  --without-links-dir --without-doc-dir --without-html-dir --without-examples-dir
make
make install
make check
```

The initial parallel build attempted to use `gplc` before creating it.
Building `make -C EnginePl top_comp` first resolved that build-order issue,
after which `make -j4` succeeded. Serial `make` is shown above to avoid
depending on the parallel ordering. The private `install/bin` must be on
the compilation command's PATH so `gplc` can locate `pl2wam` and other tools;
the experiment Makefile supplies it.

## Why the single-runtime boundary matters

At the pinned source revision:

- `gprolog/src/BipsPl/foreign_supp.c:74` declares static `query_stack` and
  `query_stack_top`; `Pl_Query_Call()` pushes the current choice point.
- `foreign_supp.c:399` implements `Pl_Query_Next_Solution()` against the
  current `pl_query_top_b`, with no query argument.
- `foreign_supp.c:422` onward pops the most recent query on query end.
- `gprolog/src/EnginePl/engine.c:449` onward maintains a nested C jump-buffer
  and machine-register-save chain around native Prolog execution.

These constraints motivate one process worker per active query lifetime.
Each worker preserves its own continuation until completion, cancellation or
expiry, then releases its resources.

## Implementation scope

The project targets ISOBASE: source loading and isolation, query execution,
answer pagination, the HTTP `/call` contract and the remaining profile
facilities. See [isobase/README.md](isobase/README.md) for the implementation
plan. ISOTOPE may follow after ISOBASE is complete.
