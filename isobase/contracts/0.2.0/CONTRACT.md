# ISOBASE shared contract 0.2.0 — draft

This version records C04's dispositions for all 42 previously labelled GNU host
boundaries. It supersedes 0.1.0 for new tests while retaining that version and its
historical evidence. It changes the agreed target; it does **not** assert that
either current node implements every decision. Implementation fixes remain in
K02/K03/K05/K06 and related work. Neither comparison runtime is changed here.

## Authority and scope

Applicable ISO core requirements, including the selected corrigenda, take priority
for included language features. ISOBASE-specific behavior is a project decision;
we label it as such rather than attributing HTTP or RPC rules to ISO. The required
97 predicate/arities, three allowed source directives and optional hashing entry
are unchanged. Full clause-level ISO and grammar-standard audits remain open.

The reviewed [TU Wien material](https://www.complang.tuwien.ac.at/ulrich/iso-prolog/)
is a useful source of discriminating tests, not a blanket checklist for this
restricted node. Select by feature and context. Syntax/serialization tests that
use a reader or writer may be adapted to the node boundary; direct ambient I/O
need not be exposed. Unselected tests are **unreviewed**, not presumed irrelevant.
`iso-test-selection.json` records ten selected/adapted cases, row identifiers,
retrieval hashes, expected outcomes and inclusion/exclusion rules. No downloaded
suite is executed, and passing this selection is not full ISO conformance.

## Decisions

`boundary-decisions.json` is the machine-readable record. B01–B42 correspond in
order and identity to the frozen observations in status-evidence.json. Every row
has a disposition, rationale, responsible implementation(s), follow-up work and,
for required common behavior, an implementation-independent executable probe.

| Rows | Agreed policy | Required work |
|---|---|---|
| B01–B03, B05 | Common exact integer range at least -2^60 through 2^60-1 for this 64-bit profile. Outside that range, documented wider exact integers or bounded-overflow behavior are legitimate differences. No silent float approximation. | Both document limits; K02 must audit within-range semantics and bounded overflow. GNU does not need bignums merely to imitate SWI. |
| B04 | `**/2` produces a float. The finite result of `2**60` must not be forced through bounded integer exponentiation. | Both ISOBASE adapters: remove GNU's SWI-matching integer-result wrapper and arrange ISO float-power semantics in SWI's ISOBASE context. |
| B06 | Double-quoted source uses codes in the portable profile. Code values represent decoded Unicode scalars, not UTF-8 bytes. | Configure/adapt SWI's node reader; complete GNU Unicode double-quote work in K03. The current probe covers ASCII only. |
| B07 | The portable Unicode atom/wire domain excludes U+0000 and surrogates. A host can support additional characters locally; that does not extend the shared domain. | Document the restriction on both nodes; no need to remove SWI's local NUL support. This is a qualified portable character policy, not full Unicode parity. |
| B08–B11, B22–B23 | Parsing integer text outside the common range is a limit-dependent case. The current GNU diagnostic is not declared an ISO-mandated error subtype. | K02 audits precise rejection semantics; both document supported ranges. These inputs are not counted as portable semantic passes. |
| B12–B21 | Portable number conversions exclude rational, non-finite and non-ASCII-digit lexical forms. Reject with a syntax error rather than silently reinterpret. Character lists and code lists retain their distinct types. | SWI node conversion policy for these extensions; **both** adapters need review for the separate character/code coercion issue revealed by selected tests. |
| B24–B25, B31–B32 | The baseline accepts finite caller deadlines in 0..300 seconds and rejects values outside it before I/O, with a timeout domain error. Owner limits may tighten execution further. | SWI option validation; retain GNU rejection. This is resource/API policy, not an ISO arithmetic rule. |
| B26–B30 | Closed RPC option vocabulary. Unknown options, public HTTP headers/method/redirect switches and TLS bypass hooks are rejected. | Restrict SWI ISOBASE forwarding; credentials and transport policy belong to the owner. Do not weaken GNU validation. |
| B33–B34 | Preserve a node base path prefix, trim its terminal slash, then append `/call`. | SWI URI composition; test against a fixture serving only `/nested/call`, not against a root endpoint that hides path loss. |
| B35–B36 | A node base address cannot contain query or fragment components. Reject with an address domain error before I/O. Exact source URLs are a separate interface. | Both validators; GNU's eventual transport failure is not sufficient validation. |
| B37–B39 | Require an explicit HTTP(S) atom or Host:Port; no implicit bare `local`, `self` or `localhost` aliases. | SWI node address validation. This does not ban `http://localhost:PORT`. |
| B40–B41 | List-valued node addresses remain an optional GNU extension, outside the portable address type. | Document the extension; shared callers use atom addresses. Neither node must add/remove the extension to claim this scoped profile. |
| B42 | Malformed ports raise a catchable address domain error before I/O; silent failure is not acceptable. | Both address validators; preserve GNU's catchability but move rejection before transport. |

These limits qualify the compatibility claim: portable programs use the declared
shared range, character domain and address types. Optional extension behavior and
limit-dependent observations are reported separately, never added to the count
of required semantic successes. A selected required test that fails remains a
failure, even when both implementations fail in the same way.

For power semantics, SWI's own [function documentation](https://www.swi-prolog.org/pldoc/man?function=%2A%2A%2F2)
explicitly distinguishes its integer-result extension from the ISO float result.
The pinned GNU manual's arithmetic table also describes float output for `**`.
For character limits, the TU Wien index discusses implementation-defined processor
character sets. Number-conversion and grammar test selections point to the exact
comparison pages; historical implementation columns are not current verdicts.

## Other exposed extensions

`nth/3` and `promise_cleanup/1` are retained as explicitly GNU-local extensions,
not additions to the 97 required predicates. Shared programs must use the required
nth0/nth1 interfaces and the eventual shared cancellation contract. GNU's address
list extension has the same status. Unknown transport options do not become
extensions by being accidentally forwarded. GNU acceptance of unused `template`
and `offset` options in `rpc/3` remains K06 validation work, not a promised API.

## Remaining decisions and evidence

D01 (zero limit), D04 (full cyclic/attributed-term policy), D06 (remaining wire and
continuation semantics), and D07 (remaining resource/authentication contract) stay
open. D02/D03/D05 are resolved only for the cases and scope choices above; wider
mode/error audits remain required. C04 closes disposition of the 42 observations,
not their implementation or the broader ISO audit.

Run `make boundary-contract-test` for both nodes against the required probes and
the selected external cases. It records all outcomes before failing on unmet
requirements. `make contract-test` retains the small independent smoke suite.
`make conformance-test` remains a diagnostic comparison corpus; its old GNU-only
boundary expectations no longer count as passing conformance assertions.
