# Selected ISO conformance tests

The [TU Wien ISO Prolog collection](https://www.complang.tuwien.ac.at/ulrich/iso-prolog/)
is a source of tests for the shared profile. Passing its entire collection is not
an ISOBASE requirement. Selection depends on the language feature, argument mode,
portable data domain and execution context—not on which runtime already passes.
Unselected cases remain unreviewed; a failing included case stays a failure.

Contract [0.2.0](contracts/0.2.0/CONTRACT.md) freezes ten initial cases in
[the selection manifest](contracts/0.2.0/iso-test-selection.json), including source
URLs, row identifiers, retrieval hashes, adaptations and explicit expected results:

| Source | Selected rows | Purpose |
| --- | --- | --- |
| [Syntax tests](https://www.complang.tuwien.ac.at/ulrich/iso-prolog/conformity_testing) | 56, 59, 315 | Negative integer syntax with layout/comments; hex character escape |
| [number_chars tests](https://www.complang.tuwien.ac.at/ulrich/iso-prolog/number_chars) | 8, 14, 21, 31 | Character/code distinction, signed input with layout, partial output list; use corrected outcomes |
| [phrase tests](https://www.complang.tuwien.ac.at/ulrich/iso-prolog/phrase) | 4, 9, 14 | Terminal lists, conjunction and alternatives |

Reader/writer examples are adapted to the node's source and result boundary;
they do not require opening public streams. Tests of excluded runtime mutation,
unrestricted I/O or unsupported optional facilities do not automatically expand
the profile. Tests outside the common integer/character domain require a separate
limit audit. Historical result columns and superseded interpretations are not
normative answers. Full clause and grammar-standard audits remain V01/K04 work.

Run `make boundary-contract-test`. It checks both pinned nodes against the same
explicit expectations, plus 29 required boundary decisions. It fails on any
unmet requirement and records every result with provenance. The first run gave
GNU 33/39 and SWI 5/39; these deliberately selected boundary checks are not an
overall conformance percentage. See [saved results](boundary-evidence.json).

The selection exposed GNU adapter behavior that had copied SWI extensions:
integer results for `**/2` and numeric codes accepted by `number_chars/2`.
GNU now passes these three requirements after restoring native float power and
enforcing the declared numeric list representation. After the subsequent node-address validation corrections its current result is 39/39;
the pinned SWI result remains 5/39. The initial run is retained in the evidence history.
