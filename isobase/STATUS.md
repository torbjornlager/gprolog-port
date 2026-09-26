# Current ISOBASE reconciliation status

This is the current status entry point. Generated from `status-obligations.json`,
`predicate-inventory.json`, saved evidence and contract decisions; run `make status-check`
to detect mapping or generated-file drift. Update inputs deliberately, then
run `python3 status_report.py` to regenerate. This is an audit index, not
a replacement contract or a claim that every mode has been tested.

Contract: **0.2.0 (draft)**. Authority: applicable ISO requirements
and explicit shared ISOBASE decisions. SWI is a comparison implementation.
Either node, both, or the contract/tests may need changes. C03 creates the
mapping; C04 settles the 42 dispositions. Implementation work remains in K01–K11.

## Evidence and confidence

- Historical contract 0.1.0 run (2026-09-26): **1276/1277**, including 42 GNU-specific outcomes in the old score.
- Categories: 1233 reference comparisons, 42 explicit GNU boundaries,
  and 2 GNU-only guards. Some comparisons establish only rejection/catchability.
- Current comparison accounting leaves those 42 observations unscored; they cannot waive required behavior.
- Contract 0.2.0 targeted checks: **GNU 39/39; SWI 5/39**. These cover 29 boundary requirements and ten selected TU Wien tests.
- The 13 limit/extension dispositions are not counted as passes. Required failures remain failures.
- Full targeted outcomes and run provenance: [boundary-evidence.json](boundary-evidence.json).
- Current broad comparison: **1203/1235**; 42 unscored observations. 31 disagreements follow the GNU numeric corrections; RPC `limit(0)` also remains unresolved (D01/K01).
- C01 separately ran seven pinning tests and six independent assertions.
  Local/compiled/security/HTTPS/endurance successes reported in SECURITY.md
  are historical evidence, not new executions during this reconciliation.
- The RPC suite stops at its zero-limit assertion, so its later checks
  cannot be described as passing in the current run merely because they exist.
- No required predicate has exhaustive mode coverage or an independently
  completed ISO-clause audit. Mapping a test file is not proof of coverage.
- Saved revisions, result digest, failing case and all 42 boundary observations
  are retained in [status-evidence.json](status-evidence.json). They are observations,
  interpreted by the current contract dispositions. New results must be reconciled explicitly.

## Required predicates and exclusions

All **97 required predicate/arities** and the one optional `crypto_data_hash/3`
entry match both contract 0.2.0 and its pinned acceptance snapshot. Each
required predicate has an implementation and evidence entry in
[PREDICATE_CHECKLIST.md](PREDICATE_CHECKLIST.md). Optional hashing is unavailable;
it is not a missing required ISOBASE predicate. Actors, sessions, general I/O
and runtime mutation remain outside the restricted callable profile.
The generator now fails if the snapshot inventory and contract sets diverge.

The frozen source snapshot is evidence about the pinned Trinity implementation.
It must not silently override a future independently agreed contract version.

## Non-predicate obligations

| Obligation / items | Current implementation and evidence | Open decision / remaining work |
| --- | --- | --- |
| **source-directives**: `dynamic/1`, `multifile/1`, `discontiguous/1` | implemented; selected declaration tests. Implementation: [source.pl](source.pl), [compile_shared.pl](compile_shared.pl). Evidence entry points: [source_tests.py](source_tests.py), [shared_db_tests.py](shared_db_tests.py), [compiled_tests.py](compiled_tests.py). | K08: Complete invalid declaration, loading-order and compiled/snapshot parity modes. |
| **dcg-source**: `[]//0`, `'.'//2`, `,//2`, `;//2`, `\|//2`, `{}/1`, `call//1`, `phrase//1`, `!//0`, `\+//1`, `->//2` | implemented with selected syntax/context coverage. Implementation: [source.pl](source.pl), [policy.pl](policy.pl). Evidence entry points: [source_tests.py](source_tests.py), [dcg_mode_cases.py](dcg_mode_cases.py), [mode_cases.py](mode_cases.py). | K08 V02: Module contexts, remaining malformed/variable grammars; applicability of separate grammar standards remains undecided. |
| **arithmetic-expressions**: `+/2`, `-/2`, `*/2`, `///2`, `//2`, `rem/2`, `mod/2`, `-/1`, `abs/1`, `sign/1`, `float_integer_part/1`, `float_fractional_part/1`, `float/1`, `floor/1`, `truncate/1`, `round/1`, `ceiling/1`, `+/1`, `div/2`, `**/2`, `sin/1`, `cos/1`, `atan/1`, `exp/1`, `log/1`, `sqrt/1`, `max/2`, `min/2`, `^/2`, `asin/1`, `acos/1`, `atan2/2`, `tan/1`, `pi/0`, `>>/2`, `<</2`, `/\\/2`, `\\//2`, `\\/1`, `xor/2` | native evaluation with selected wrappers; ISO float output for ** restored under contract 0.2.0; not an exhaustive functor/mode audit. Implementation: [policy.pl](policy.pl), [prologue.pl](prologue.pl), [terms.c](terms.c). Evidence entry points: [boundary_cases.py](boundary_cases.py), [higher_arithmetic_cases.py](higher_arithmetic_cases.py), [numeric_mode_cases.py](numeric_mode_cases.py), [numeric_contract_tests.py](numeric_contract_tests.py). | D02 K02 V03: Verify required expression set and all domains/errors independently; native evaluator can accept additional GNU expressions. |
| **rpc-options**: `limit/1`, `once/1`, `timeout/1`, `http_timeout/1` | implemented; zero/timeout/unknown-option differences recorded. Implementation: [rpc.pl](rpc.pl), [transport.c](transport.c). Evidence entry points: [rpc_option_cases.py](rpc_option_cases.py), [rpc_boundary_cases.py](rpc_boundary_cases.py), [rpc_tests.py](rpc_tests.py). | D01 D05 K01 K06: Resolve option validation and binding order against shared decisions, not SWI alone. |
| **promise-options**: `template/1`, `offset/1` | implemented for promises; GNU common validator also accepts these in rpc/3. Implementation: [rpc.pl](rpc.pl). Evidence entry points: [rpc_option_cases.py](rpc_option_cases.py), [rpc_tests.py](rpc_tests.py). | D05 K06: Catalog describes these as promise-only. GNU rpc uses its own template and begins at offset zero; decide rejection versus explicitly permitted ignored options. |
| **yield-options**: `timeout/1`, `on_timeout/1` | implemented with selected non-consuming timeout/callback tests. Implementation: [rpc.pl](rpc.pl), [policy.pl](policy.pl), [transport.c](transport.c). Evidence entry points: [rpc_tests.py](rpc_tests.py), [policy_tests.py](policy_tests.py), [conformance_tests.py](conformance_tests.py). | D05 K07 S08: Complete mismatch, callback, guard and cancellation states; do not copy stale queue behavior. |
| **source-options**: `src_text/1`, `src_list/1`, `src_predicates/1`, `src_uri/1` | implemented; exact-source URL and order checks exist. Implementation: [rpc.pl](rpc.pl), [source.pl](source.pl), [text.pl](text.pl), [transport.c](transport.c). Evidence entry points: [rpc_source_tests.py](rpc_source_tests.py), [rpc_option_cases.py](rpc_option_cases.py), [rpc_boundary_cases.py](rpc_boundary_cases.py), [https_tests.py](https_tests.py). | D05 K06 K08 K11 S01: GNU URI source is HTTP(S) only; reference catalog also describes file/relative forms. Decide portable forms and enforce destination/aggregate bounds. |
| **http-parameters**: `goal`, `template`, `src_text`, `format`, `offset`, `limit`, `once`, `timeout` | implemented; duplicate/unknown parameters rejected. Implementation: [http.c](http.c), [query.pl](query.pl), [worker.c](worker.c). Evidence entry points: [http_tests.py](http_tests.py), [differential_tests.py](differential_tests.py), [request_reader_tests.py](request_reader_tests.py). | D01 D06 K01 K09: Complete encoding, size, formal-error and fresh/resumed limit modes. |
| **answer-encoding**: `JSON bindings`, `Prolog success/failure/error envelopes`, `template/goal sharing`, `Unicode and operators` | implemented with selected serialization tests. Implementation: [query.pl](query.pl), [text.pl](text.pl), [worker.c](worker.c), [terms.c](terms.c), [http.c](http.c). Evidence entry points: [http_tests.py](http_tests.py), [higher_arithmetic_cases.py](higher_arithmetic_cases.py), [boundary_cases.py](boundary_cases.py), [compiled_tests.py](compiled_tests.py). | D02 D03 D04 D06 K09: Resolve number/string/cycle boundaries and exact formal versus diagnostic errors. |
| **continuations**: `live pages`, `cache keys`, `replay on miss`, `once`, `expiry`, `eviction`, `disconnect` | implemented; text keys and owner-wide continuations. Implementation: [http.c](http.c), [supervisor.c](supervisor.c). Evidence entry points: [http_tests.py](http_tests.py), [eviction_tests.py](eviction_tests.py), [supervisor_tests.py](supervisor_tests.py), [endurance_tests.py](endurance_tests.py). | D06 K10 S04: Agree replay/key semantics and any per-principal ownership before tenant claims. |
| **remote-lifecycle**: `RPC enumeration`, `promise reference lifetime`, `yield consumption`, `transport failure`, `cancellation` | implemented; node address validation precedes source/network I/O in both RPC and promises; asynchronous error/cleanup differences remain. Implementation: [rpc.pl](rpc.pl), [transport.c](transport.c). Evidence entry points: [rpc_tests.py](rpc_tests.py), [rpc_source_tests.py](rpc_source_tests.py), [https_tests.py](https_tests.py), [rpc_address_tests.py](rpc_address_tests.py). | D05 K07: Specify portable outcomes; current tests abort at the known zero-limit assertion before later RPC cases. |
| **shared-source**: `snapshot`, `native bundle`, `private shadowing`, `clause inspection`, `source exports` | implemented in both loading modes. Implementation: [source.pl](source.pl), [compile_shared.pl](compile_shared.pl), [build_shared.py](build_shared.py), [policy.pl](policy.pl). Evidence entry points: [shared_db_tests.py](shared_db_tests.py), [compiled_tests.py](compiled_tests.py), [proof_tree_tests.py](proof_tree_tests.py). | K08 S12: Complete source interaction coverage; shared application clauses are intentionally readable. |
| **runtime-capabilities**: `implementation/1`, `persistent/1`, `inbound_addressable/1`, `dom/1`, `actor_isolation/1`, `hard_termination/1` | GNU host declarations; not SWI equality requirements. Implementation: [prologue.pl](prologue.pl). Evidence entry points: [conformance_tests.py](conformance_tests.py). | V01: Validate truthful worker capabilities; OS process separation does not imply an OS privilege sandbox. |
| **execution-denials**: `general I/O`, `runtime mutation`, `actors/sessions`, `owner node control`, `module bypass`, `arbitrary directives` | default-deny guards; selected direct/indirect checks. Implementation: [policy.pl](policy.pl), [source.pl](source.pl). Evidence entry points: [policy_tests.py](policy_tests.py), [source_tests.py](source_tests.py), [conformance_tests.py](conformance_tests.py). | S08 S09: Complete every callback/source/compiled entry point; excluded profile families remain excluded. |
| **inbound-access**: `bearer token`, `Host`, `Origin`, `fetch metadata`, `token file`, `open fixture mode` | implemented for authenticated local owner scope. Implementation: [http.c](http.c), [http_security.h](http_security.h). Evidence entry points: [security_tests.py](security_tests.py), [request_reader_tests.py](request_reader_tests.py). | D07 S03 S04 S10 S13: Credential lifecycle and HTTP audits; network/multi-principal deployment unsupported. |
| **outbound-access**: `destination restrictions`, `destination credentials`, `TLS`, `redirects` | exact origin/IP and optional HTTPS RPC endpoint credential grants; deny by default; no inbound/source credential forwarding; proxies and redirects disabled. Implementation: [transport.c](transport.c), [rpc.pl](rpc.pl), [outbound_policy.h](outbound_policy.h), [outbound_credentials.h](outbound_credentials.h). Evidence entry points: [https_tests.py](https_tests.py), [rpc_source_tests.py](rpc_source_tests.py), [outbound_policy_tests.py](outbound_policy_tests.py), [outbound_socket_tests.py](outbound_socket_tests.py), [outbound_credentials_tests.py](outbound_credentials_tests.py), [credential-evidence.json](credential-evidence.json). | D07 S01 S02 S14: S01 isolated-deployment network enforcement; S03 credential lifecycle; stronger secret isolation and further transport audit. |
| **resource-lifecycle**: `deadlines`, `response bounds`, `sampled query/aggregate memory`, `admission`, `cleanup` | sampled limits implemented; hard OS containment missing. Implementation: [http.c](http.c), [supervisor.c](supervisor.c), [memory.h](memory.h), [memory_tree.h](memory_tree.h), [transport.c](transport.c). Evidence entry points: [supervisor_tests.py](supervisor_tests.py), [memory_tests.py](memory_tests.py), [total_memory_tests.py](total_memory_tests.py), [endurance_tests.py](endurance_tests.py). | D07 S05 S06 S07 S11 K11 V05: Hard containment, abrupt-death cleanup, fairness and aggregate transfer budgets remain. |
| **gnu-extensions**: `nth/3`, `promise_cleanup/1` | exposed outside required/optional contract predicate inventory. Implementation: [policy.pl](policy.pl), [rpc.pl](rpc.pl), [transport.c](transport.c). Evidence entry points: [policy_tests.py](policy_tests.py), [rpc_tests.py](rpc_tests.py). | C04 K06 K07: C04 retains these as GNU-local optional extensions; shared API validation and cancellation work remain K06/K07. |

Arithmetic items above are enumerated from the pinned Trinity builtin catalog
(`f237dd5c806893dad17c95cad9a2dc1692a73607`). The source path and digest
are in status-obligations.json. This enumerates the audit surface without
declaring every listed functor an ISO requirement or claiming the GNU evaluator
rejects every unlisted expression. DCG, option and wire rows are separate
obligations; counting them as callable predicates would misstate coverage.

## Disagreement register and responsibility

| Issue | Evidence / classification | Next owner/action |
| --- | --- | --- |
| RPC limit(0) | Recorded failure: SWI raises a positive-integer error; GNU returns failure. | D01/K01: shared API decision, then change the affected node(s) and tests. No presumption GNU is wrong. |
| 23 numeric/text boundary cases | Seven host_boundary and 16 numeric_lexical observations, including range, strings, NUL and numeric lexical forms. | C04 decided portable ranges, float power, codes and lexical policy. K02/K03 implement and audit remaining modes; GNU float power and numeric character/code distinction are corrected with independent regressions; the pinned SWI adapter still fails these requirements. |
| 19 RPC option/address boundary cases | Two rpc_option_modes plus seven options, seven URI and three alias observations. | GNU now passes all 29 boundary requirements, including address errors before source I/O; SWI corrections and broader K05–K07 audits remain open. |
| Cyclic terms/errors, capabilities and asynchronous cleanup | Broader differences described in TEXT_NUMERIC_BOUNDARY.md and RPC_BOUNDARY.md; not all are among the 42 expected-GNU rows. | D04/D05/V01: separate valid host capabilities from required semantics and deliberately safer cleanup. |
| Extra callable surface | GNU exposes nth/3 and promise_cleanup/1 outside the contract inventory. Targeted worker probes are stored in status-evidence.json. | C04: retain documented GNU-local extensions; K06/K07 still govern shared API and cleanup. |
| rpc/3 template and offset | Code inspection: common GNU validator accepts both; rpc builds its own variable template and starts at offset zero. Pinned catalog describes these as promise-only. | D05/K06: verify both peers with dedicated cases and choose rejection or an explicit extension. Current evidence is inspection, not a new differential result. |
| Authentication, network access, resource limits | Local owner auth, outbound origin/IP restrictions and scoped HTTPS RPC credentials exist; OS/network isolation and credential lifecycle review remain unfinished. | D07/S01–S16: implementation controls governed by THREAT_MODEL.md, not conformance to unsafe peer behavior. |
| Historic reference defects | Prior ledger reports call_nth guarding, grammar-closure and source-composition fixes. These reports are history, not current additional failing cases. | Preserve regression coverage; reopen only with reproducible current evidence. |
| Stale docs | Redirects described as absent; zero limits described as current SWI agreement; auth described as wholly missing; obsolete counts presented as current. | GNU project documentation: corrected by C03. Runtime behavior and locked contract unchanged. |

## Reading the other documents

- [CONFORMANCE.md](CONFORMANCE.md): historical audit narrative and test methodology.
- [RPC_BOUNDARY.md](RPC_BOUNDARY.md) and [TEXT_NUMERIC_BOUNDARY.md](TEXT_NUMERIC_BOUNDARY.md): detailed behavior and limits; historical batch counts are labelled.
- [SECURITY.md](SECURITY.md), [THREAT_MODEL.md](THREAT_MODEL.md) and [MEMORY_LIMITS.md](MEMORY_LIMITS.md): controls and deployment assumptions.
- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md): outstanding work and completion criteria.
- [contracts/0.2.0/CONTRACT.md](contracts/0.2.0/CONTRACT.md): active draft decisions, portable restrictions and implementation responsibilities.
