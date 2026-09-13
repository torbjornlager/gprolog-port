# ISOBASE conformance ledger

Target: the documented portable ISOBASE profile and `/call` contract in the
Trinity demonstrator, checked against its current local implementation.
This is an implementation and test ledger, **not a claim of full conformance**.
A passing sample suite is not exhaustive validation of every mode or error case.

## Contract sources

- `/Users/lager/trinity-demonstrator/docs/WEB_PROLOG_BUILTINS.md`
- `/Users/lager/trinity-demonstrator/docs/WEB_PROLOG_BUILTINS_ACCEPTANCE_MATRIX.md`
- `prolog/web_prolog/node_profile_policy.pl`, `node_call_context.pl`, `rpc.pl`,
  `node_engine.pl`, and `actor_io_template.pl` in that checkout.

The acceptance matrix distinguishes portable predicates, source directives,
optional local extensions, and predicates excluded from ISOBASE. When the
implementation contradicts its documented restrictions, the discrepancy is
recorded below rather than copied into this runtime.

## Implemented contract families

| Family | Implementation and evidence |
|---|---|
| Control, unification, type/term operations | Native operations and guarded rewrites; conformance, worker and policy tests |
| Arithmetic and atom processing | GNU numeric bounds; compatibility wrappers for integer rounding, integer powers, float-part operations, numeric atom length and variable-position `arg/3` |
| All-solutions and higher-order operations | Scoped `findall`, `bagof`, `setof`, `call/1-8`, `maplist/2-5`, `foldl/4-7`; all listed arities sampled, including open-list enumeration, variable sharing, cuts, exceptions and execution guards |
| Prologue | `member`, `append`, `length`, `between`, `select`, `succ`, `nth0/3-4`, `nth1/3-4`, `call_nth/2`; tests include insertion, enumeration, nested counters and formal argument errors |
| Timing | `time/1` preserves nondeterminism and exceptions; CPU diagnostics go to worker stderr. `/call` exposes no terminal timing event, as in the reference HTTP path |
| Runtime properties | Six host properties implemented; values describe the GNU query runtime rather than pretending to offer SWI actors |
| Source and DCGs | Facts/rules, DCG expansion, dynamic/multifile/discontiguous declarations; arbitrary directives and runtime overrides rejected |
| Shared/private source isolation | Local shadowing, protected shared resolution and read-only local/shared `clause/2`; tested in snapshot and compiled modes |
| RPC, promises, yield | Three interoperation directions, source transfer, pagination, non-consuming wait timeout, cancellation; references are opaque ten-digit integers scoped to one query |
| HTTP answers | Goal/template sharing, Prolog and JSON formats, variable visibility including anonymous helper goals, default limit 10,000,000,000 |
| Pagination/cache | Live continuations, offset replay after miss, oldest-idle eviction, active-query protection, idle expiry and zero-sized pages |
| Lifecycle/resource behavior | Query deadlines, stack/output bounds, disconnects, worker reaping; 400 queries / 800 pages with eight concurrent clients |

The zero-limit behavior is deliberately the observed reference behavior: a fresh
zero-limit query returns `failure` without executing its goal; zero on a live
continuation resumes with the default page limit. Source and goal validation
still apply. The API accepts at most 10,000,000,000 as an explicit page size.

`runtime_property/1` reports `implementation(gnu_native)`, `persistent(false)`,
`inbound_addressable(false)`, `dom(false)`, `actor_isolation(os_process)` and
`hard_termination(true)`. These describe the disposable query worker: it has no
persistent session DB or inbound actor address. The host HTTP node itself is
long-lived and reachable. They are host capabilities, not portable guarantees.

## Test entry points

- `make conformance-test`: formal term comparisons with a temporary SWI node,
  GNU-only policy assertions, HTTP response comparison and concurrency endurance.
- `make test rpc-test compiled-test`: existing worker, loader, supervisor,
  HTTP, eviction, source isolation, transport and native-compiler regressions.
- `ISO_COMPILED_NODE=./build/<bundle>/isobase-node python3 conformance_tests.py`
  and `endurance_tests.py`: run the same assertions against compiled shared code.
- `conformance-results.json`: per-case goal, expected/actual response and result.

Formal Prolog results are compared up to variable renaming. Catchable argument
errors are tested by catching `error(Form,_)` inside the query and comparing
`Form`, leaving host-specific context text out of the assertion. Policy-rejection
cases check rejection, not identical diagnostic wording. Host capability values
and the explicitly identified guard regressions are GNU-only assertions; they
are not counted as SWI behavioral matches.

## Guard and shared-inspection correction

`call_nth(halt,1)` previously terminated a disposable SWI test server.
The Trinity checkout now traverses and guards `call_nth/2`, including variable
goals and source bodies; those cases are compared against SWI again.

Shared `clause/2` access in SWI was intentional, despite the acceptance matrix
having described it as local-only. Example 18 depends on this behavior. The
matrix is corrected, and GNU now exposes original local/shared application
clauses in both interpreted and compiled modes, preserving local shadowing and
shared caller resolution. Runtime introspection and mutation remain blocked.
Distributed proof-tree regressions ship only the interpreter across two real
shared databases and check all three complete proofs.

`yield/3` timeout callbacks are separately checked for GNU guard enforcement;
no claim is made here that the corresponding reference path was tested unsafe.
All termination probes use disposable nodes, never a live service.

## Relational modes and DCG audit

The relational-mode audit expanded the corpus to 196 samples (194 compared with SWI and two GNU-only
policy checks), up from 152. `mode_cases.py` adds closure arities 1–8,
`maplist/2-5`, `foldl/4-7`, open-list generation, nondeterministic closures,
closure cuts, exceptions, and source DCGs with conjunction, disjunction,
if-then-else, negation, cuts, embedded goals and remainder lists.

The audit corrected premature commitment to the empty-list solution in
`maplist` and `foldl`. For example, `maplist(=(a),L)` now yields `[]`, `[a]`,
`[a,a]`, etc. The corpus bounds such searches using the HTTP page limit;
its harness now respects per-case limits rather than overwriting them.
`phrase/3` validates the outer list cells and raises a catchable list type error
for scalar arguments, while allowing open and partial lists. Applied numeric
closures now report the same formal atom type error as the reference.

One reference discrepancy remains: the SWI node rejects
`phrase(([a],{X=b},[X]),L)` with a missing `','/4` procedure error, although
GNU returns `L=[a,b]` and the equivalent source DCG works on both. GNU retains
this behavior; `source_tests.py` checks its answer independently. This case is
not counted as a SWI match. No SWI runtime changes were made in this audit.

## Text and numeric audit

See [TEXT_NUMERIC_BOUNDARY.md](TEXT_NUMERIC_BOUNDARY.md) for the tested contract,
remaining lexical/string/NUL/integer limitations, and the distinction between
SWI matches and explicit host-boundary checks. The suite now has 253 cases:
244 SWI comparisons, two GNU-only guard checks and seven host boundaries.
UTF-8 atom operations and serialization are covered, including compiled source
and RPC transfer; arbitrary SWI string or bignum equivalence is not claimed.

## RPC and promise audit

[RPC_BOUNDARY.md](RPC_BOUNDARY.md) records ten shared GNU/SWI promise-state
checks and additional GNU transport, Unicode source-transfer and cyclic-error
regressions. These are separate from the 253-case term corpus. Redirected HTTP(S)
source now works within a five-hop bound; protocol/transport failures free slots.
The remaining asynchronous error and cleanup differences are explicit.
Seventeen additional local HTTPS checks verify certificate failures, owner CA
configuration, redirect limits and source-fetch deadlines; these are GNU
transport checks and do not increase the SWI equivalence count.

## Predicate checklist and first mode audit

[PREDICATE_CHECKLIST.md](PREDICATE_CHECKLIST.md) expands the acceptance matrix
into 97 required callable predicate/arities plus one optional extension. The
machine-readable companion is `predicate-inventory.json`; regenerate both with
`python3 predicate_inventory.py`. Test references are entry points, not claims
of exhaustive coverage. Source syntax, expression functors and options are
listed as separate obligations.

The 58-case first batch found 18 discrepancies, now corrected. Bound and partial
text arguments now follow the sampled SWI coercion/error behavior. `length/2`
checks its numeric argument before the list, fails on length/tail variable
aliasing, and accepts finite list spines containing cyclic elements. `terms.c`
uses actual list-cell identity to detect cyclic spines without structural
comparison looping. Cyclic-spine catchability is compared; GNU's finite
representation error remains distinct from SWI's cyclic list error term.

After the first batch, the corpus had 311 passing cases: 302 SWI comparisons (including the
coarser catchability check), two GNU-only guard checks and seven explicit host
boundaries. Historical counts above describe earlier audit batches.

## Conversion-mode audit

The next checklist batch adds 114 character/number conversion checks in
`conversion_mode_cases.py`. The initial 96 cases exposed 45 discrepancies;
18 lexical checks then added decimal/signed exponent and malformed/overflow
coverage. Input character/code lists, partial output behavior and the sampled
error precedence now match SWI. Integer mantissas with exponents are normalized
before native parsing; non-finite parse results raise `syntax_error(float_overflow)`.

After the second batch, the corpus had 425 passing cases: 416 SWI comparisons (including the
previous cycle catchability check), two GNU-only guards and seven explicit host
boundaries. Further numeric syntax, formatting, round trips and range boundaries
remain listed in the predicate checklist; this is not a complete lexical audit.

## List-mode audit

`list_mode_cases.py` adds 148 cases for member/append/select, nth0/nth1 with
and without remainder arguments, succ and between. The first 127 exposed six
discrepancies: succ now validates its first nonvariable argument before unifying
the other, and between accepts `inf` and `infinite` upper bounds. Expanded
checks cover lazy enumeration, indirect calls and cyclic invalid arguments.
Improper lists and bounded access to cyclic spines match the sampled SWI behavior.

After the third batch, the corpus had 573 passing cases: 564 SWI comparisons (11 compare cyclic
error catchability rather than exact error terms), two GNU-only guards and seven
explicit host boundaries. Separate policy tests check that infinite enumeration
raises `evaluation_error(int_overflow)` when advancing beyond GNU's maximum
integer. Compiled shared-clause tests cover the new wrappers and remainder modes.
These are selected modes, not an exhaustive list or determinism audit.

## Numeric lexical and round-trip audit

`numeric_mode_cases.py` adds 236 cases, including 16 explicit host-boundary
assertions. Conversions accept the sampled leading plus signs, integer digit
separators and base-2 through base-36 radix notation. The whole integer token is
validated before separators are removed; malformed fractional/exponent separators
remain errors. Native-range integer overflow in text remains a catchable syntax
error, without conversion to floating point.

Float conversion uses increasing significant-digit precision until parsing the
output returns the same binary64 value (including the sign of zero). Decimal
points preserve float types. The sampled output spellings match SWI, including
0.1 and subnormals; 128 deterministic binary64 values round-trip through each
converter. This is not a proof of all SWI float formatting or parser equivalence.
Source-literal parsing and general term serialization retain their GNU behavior.

After the fourth batch, the corpus had 809 passing cases: 784 SWI comparisons (including 11 coarser
cyclic-error checks), two GNU-only guards and 23 explicit host boundaries.
The new boundaries cover out-of-range integers, rationals, non-finite spellings
and sampled Unicode decimal digits. See TEXT_NUMERIC_BOUNDARY.md.

## Acyclic term and all-solutions audit

`term_mode_cases.py` adds 174 SWI comparisons. The first 124 exposed 19
differences. Result lists from term_variables, sort, keysort and the all-solutions
predicates are now computed independently before unifying with the requested
output. This preserves the sampled failure and exception timing. The wrappers
also align arg's compound-argument precedence, keysort's input-spine validation,
and univ's incremental output-list checks.

The samples cover functor/arg/univ modes, copied and collected variable sharing,
term ordering, sorting stability, existential grouping and exceptions raised
before an output mismatch. Full rational-tree and attributed-variable semantics,
and exhaustive determinism/choicepoint behavior are not established. A separate
GNU policy check verifies finite error handling for cyclic keysort input.

After the fifth batch, the corpus had 983 passing cases: 958 SWI comparisons (including 11 coarser
cyclic-error checks), two GNU-only guards and 23 explicit host boundaries.
Compiled shared-clause checks exercise collection, term variables, univ and sorting.

## DCG audit

`dcg_mode_cases.py` adds 75 cases. They cover inline and source grammars, empty
embedded goals, terminals, variable grammar bodies, cuts, alternatives, negation,
conditionals, call closures, pushback and partial input/remainder lists. Ten cases
compare rejection only (malformed grammar/source or forbidden embedded goals).
GNU normalizes `{}` to the empty grammar in grammar positions only and validates
terminal list spines before expansion, matching sampled SWI errors.

The audit also found a demonstrator bug: its generic closure guard invoked grammar
bodies as ordinary predicates. `control_guard.pl` now translates grammar closures
before guarded execution and restores them for source transfer. Node execution
still uses the public execution-policy checks; standalone control-guard use does
not require the node layer. Six focused SWI tests and the full T4 suite cover this
change. Running SWI deployments have not been restarted.

After the sixth batch, the corpus had 1058 passing cases: 1033 SWI comparisons, two GNU-only guards
and 23 explicit host boundaries. Comparison includes the documented coarser
cyclic-error and rejection checks. Full soft-cut syntax, rational-tree grammars
and every module/context combination remain unaudited.

## Higher-order and arithmetic audit

`higher_arithmetic_cases.py` adds 100 SWI comparisons. Higher-order samples cover
empty and improper lists, mismatches, aliasing, callback errors and grammar
closures. Arithmetic expression arguments now evaluate right-to-left as in the
sampled SWI cases; relational comparisons retain their separate operand order.
Rounding handles negative half-integers and values immediately beside a tie.
Zero raised to a negative power reports zero_divisor, and atan2 preserves signed
zero quadrants through the native math library.

The batch also found a serialization defect: a conjunction template could become
two answer-list elements. Templates are now rendered in list-element context,
preserving operator precedence and variable sharing. Tests include conjunction,
disjunction, implication, clauses and nested terms with paged responses.

After the seventh batch, the corpus had 1158 passing cases: 1133 SWI comparisons, two GNU-only guards
and 23 explicit host boundaries. Existing coarser rejection/cyclic-error checks
remain included. Full numeric boundary and module-context equivalence is not
claimed. Compiled shared-clause and sanitizer checks exercise the new behavior.

## Source and RPC option audit

`rpc_option_cases.py` adds 61 cases. Both clients call the same disposable GNU
target, isolating client option behavior from server differences. The cases cover
duplicate-option precedence, variable once/timeout values, source text/list/export
composition, source isolation, promise templates/offsets and basic URI forms.
GNU now omits an unbound remote timeout without binding it, matches sampled once
binding, and reports instantiation errors for unbound transport timeout values.

The audit found a SWI source-composition bug: foldl passed each new part before
the accumulator to a helper that expected the opposite order. The corrected
isolation.pl preserves the documented option order and each part's clause order.
Focused source-order tests and the isolation/node suites cover this change.
Running SWI deployments have not been restarted.

Two of these checks verify that rpc captures the wire goal before
option normalization, while promise captures it afterwards, as in SWI.

The corpus now has 1219 passing cases: 1192 SWI comparisons, two GNU-only guards
and 25 explicit host boundaries, including GNU's rejection of negative remote and
HTTP timeouts. Coarser rejection/cyclic-error checks remain included. Full URI,
unknown-option and validation-precedence equivalence is not established.

## Work required before a full conformance claim

- Extend the mode/error corpus beyond the current samples: additional higher-order modes, remaining DCG constructs and malformed bodies,
  partial/cyclic structures, arithmetic
  boundaries, exception timing, and source interactions.
- Establish the portable text/numeric boundary explicitly. GNU has bounded
  integers and different native string/character behavior from SWI. Unicode atom operations and selected arithmetic boundaries are now tested;
  Unicode lexical syntax, SWI strings and bignum equivalence remain gaps.
- Extend the RPC audit beyond the tested promise states, HTTP faults and 17
  local HTTPS checks: source URI forms, all option modes, TLS versions/ciphers
  and revocation behavior remain.
  See RPC_BOUNDARY.md for the tested behavior and intentional host differences.
- Expand the endurance run to longer resource-pressure scenarios. The current
  short concurrent run is not an hours-long soak or a total-memory guarantee.

`crypto_data_hash/3` is catalogued as a **local extension**, not part of the ISO
prologue; it remains unavailable. Actor, session and general I/O predicates stay
outside ISOBASE. Authentication and total-process-memory enforcement are separate
requirements before public deployment; the development node remains loopback-only.
