# Shared ISOBASE contract versions

The active version is **0.2.0 (draft)**, recording all 42 C04 dispositions and a scoped ISO test selection. The initial 0.1.0 version is retained unchanged. It versions the scope, authority rules,
initial required predicate inventory and independently stated smoke expectations.
It does not settle every semantic decision or certify either node as conformant.
See [the version document](0.2.0/CONTRACT.md) and
[comparison setup](../COMPARISON_BUILDS.md).

The source of truth is the applicable ISO Prolog requirements plus explicit
shared ISOBASE decisions. Neither SWI's behavior nor GNU's behavior automatically
supplies the expected answer. Changes may belong in either node, both, or tests.

Version policy:

- Never silently update an expectation to match the implementation under test.
- Record each semantic decision with its rationale, applicable ISO requirement
  (or ISOBASE-specific designation), consequences for both nodes, and independent
  positive/error tests. Where the standard permits implementation-defined choices,
  state the selected portable policy.
- A draft semantic change creates a new minor contract version; editorial-only
  corrections create a patch version. At 1.0 and later, incompatible requirements
  require a major version. An experiment is not an adopted contract change.
- Copy the version directory, change its version, and update the comparison lock
  hashes in the same reviewed change. Retain earlier versions and their evidence.
- Updating an implementation pin alone does not change the contract. Record why
  the pin changed, rerun independent and differential suites, and report any new
  disagreement without treating it as a GNU defect by default.
- Review and explicit acceptance of semantics are required before a draft becomes
  a release contract. Full per-clause ISO review and unresolved decisions remain
  separate checklist work; creating this baseline does not complete those audits.
