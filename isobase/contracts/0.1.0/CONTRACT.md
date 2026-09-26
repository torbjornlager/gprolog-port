# ISOBASE shared contract 0.1.0 — draft

## Authority and scope

This project targets the ISOBASE `/call` profile: portable query evaluation,
source submission and sharing, answers, pagination, RPC and promises. It does
not require the full SWI runtime, actors, ISOTOPE, sessions or arbitrary host I/O.
Security restrictions form part of the execution contract; matching an unsafe
implementation behavior is not a conformance objective.

For the standard Prolog core, the selected basis is
[ISO/IEC 13211-1:1995](https://www.iso.org/standard/21413.html), including its
2007, 2012 and 2017 technical corrigenda. ISO's catalogue lists these corrections;
this document does not reproduce the standard or claim its full text has been
audited. Clause-specific requirements and implementation-defined choices must
be verified when deciding a semantic dispute. Module and DCG specifications
are not implicitly adopted wholesale by choosing the core standard; their
applicability to the restricted profile must be recorded separately.

HTTP, RPC, promises, credentials, continuation identity and resource policy
require explicit ISOBASE decisions. ISO core does not determine their API.
GNU's ISO orientation is a useful reason to examine its behavior closely, not
proof that any particular behavior is required. SWI extensions are likewise
not automatically portable requirements.

## Versioned artifacts and their authority

- `contract.json`: version, selected standards basis, required/optional callable
  predicate inventory, source directives, open decisions and independent smoke
  cases. The inventory has 97 required predicate/arities and one optional
  extension (`crypto_data_hash/3`). Inclusion does not imply every mode is audited.
- `trinity-acceptance-snapshot.md`: historical input from Trinity commit
  `f237dd5c806893dad17c95cad9a2dc1692a73607`, path
  `docs/WEB_PROLOG_BUILTINS_ACCEPTANCE_MATRIX.md`. This snapshot supplies the
  initial inventory and comparison context; its descriptions of current SWI
  implementation restrictions are not independently normative ISO requirements.
- `proof-tree-interpreter.pl`: extracted fixture from the same commit's example
  `examples/actors/18 proof-trees.pl`. It makes the local proof-tree regressions
  independent of an external developer checkout. It is an example, not a spec.
- `comparison-lock.json` in the ISOBASE directory: comparison source revisions,
  runtime versions, baseline environment/toolchain and observed runtime binary
  fingerprints, plus integrity hashes for this version's files.

## Initial shared requirements

The two nodes are to implement the same agreed portable predicate/source
contract. Query variable sharing and ordered answers must survive serialization;
private submitted source must not become another query's program. Only accepted
source declarations may take effect; callers cannot bypass execution policy
through indirect calls or exported code. Runtime capabilities must describe the
actual host rather than claim capabilities only to match the other implementation.

The three independent cases in `contract.json` state simple unification, failure
and ordered-disjunction results in the existing Prolog response envelope. Both
implementations are tested against these explicit answers; neither supplies the
other's expected answer. They establish the mechanism for independent assertions,
not sufficient coverage of the required predicates or wire format.

## Decisions deliberately not made here

| ID | Decision still needed | Checklist |
|---|---|---|
| D01 | Zero page limits, including HTTP fresh/resumed and RPC validation | K01 |
| D02 | Integers, overflow, rationals, non-finite values and numeric limits | K02 |
| D03 | Strings, double quotes, Unicode lexical forms, escapes and NUL | K03 |
| D04 | Cyclic terms, attributed variables and wire representation | K04 |
| D05 | URI forms, RPC options, timeouts and asynchronous outcomes | K05–K07 |
| D06 | Wire errors, continuation keys and replay semantics | K09–K10 |
| D07 | Resource policy, identity and authenticated deployment contract | C02, S01–S14, K11 |

Existing tests containing GNU-specific expected results remain implementation
boundary tests. Existing differential cases remain observations of agreement.
Neither category settles these decisions. In particular, the known `limit(0)`
failure remains visible; this version neither changes the nodes nor suppresses
that failure to obtain a green comparison result.
