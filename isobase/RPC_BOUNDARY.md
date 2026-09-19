# RPC and promise audit

The GNU and SWI clients agree on the ten tested promise-state cases in
`rpc_tests.py`: missing-reference behavior, successful consumption, remote
failure/error delivery, one-shot delivery on backtracking, non-consuming wait
timeouts, timeout callbacks that fail or throw, and isolation of template
bindings. These are explicit expected outcomes checked through both HTTP nodes,
not claims of exhaustive equivalence.

## Corrections

- `src_text` supplied as Unicode code-point or character lists now uses the same
  UTF-8 conversion as the public atom predicates. Tests transfer Japanese and
  emoji source from GNU to both GNU and SWI.
- HTTP(S) requests, including `src_uri`, follow at most five redirects. The
  existing request deadline and response-size bound remain in effect. Redirects
  to other protocols are blocked. Tests cover a relative source redirect with
  a nonempty intermediate body, a redirect loop, a file-scheme redirect and
  an HTTP 503 response.
- Cyclic option terms raise a finite `representation_error(cyclic_term)`.
  The previous error contained the cyclic term itself, which GNU could hang
  copying. Explicit cyclic exception balls are now guarded before native
  `throw/1`; serialization also checks for cycles. HTTP and direct-worker
  regressions check prompt errors, including a catchable promise validation error.

## Deliberate differences and remaining gaps

- GNU transport/protocol errors are catchable exceptions and release the promise
  slot. Tests exercise 24 successive failures of each kind, beyond the 16-slot
  capacity. SWI's asynchronous transport path can log an error without delivering
  a message, leaving a waiter pending. That behavior is not copied.
- `promise_cleanup/1` is exposed as a GNU helper. The SWI RPC module defines it,
  but it is not exposed through the tested ISOBASE HTTP execution context. Its
  GNU cleanup tests are therefore not counted as common API matches.
- GNU `yield/3` consumes a delivered reply even if the requested message does not
  unify. SWI consumes the queue message but can retain a stale queue mapping on
  failed unification. The GNU behavior avoids retaining that stale state.
- Arbitrary cyclic terms are not a supported transport representation. These
  guards fix the tested error paths; all native built-in cyclic-argument modes
  have not been audited.
- The HTTPS checks below cover selected certificate and connection failures.
  Redirect-policy equivalence, source-URI lexical forms, all option modes,
  revocation behavior and TLS-version/cipher combinations remain unaudited.
  The five-hop redirect limit is an explicit resource bound, not a claim that
  SWI uses the same limit.

Run `make rpc-test`; set `ISO_WORKER` and `ISO_COMPILED_NODE` to test a compiled
bundle. `make test compiled-test conformance-test` covers the surrounding worker,
shared-source, HTTP and lifecycle behavior.


## HTTPS and source-fetch audit

`make https-test` runs 17 local checks. `make rpc-test` includes them too.
The fixture uses Python's SSL server and OpenSSL to generate a temporary CA and
valid, expired and wrong-host certificates. It needs an OpenSSL supporting
`x509 -not_before/-not_after` (tested with 3.6.1); `OPENSSL` can select its path.
No external service or system trust-store modification is involved.

The checks cover trusted/untrusted HTTPS, expiry, hostname mismatch, a missing
CA file, a TLS-to-plain-HTTP handshake failure, successful fifth and rejected
sixth redirects, HTTP/HTTPS timeouts and source 404s, actual HTTPS source
compilation/execution, and 24 consecutive failed promises without slot exhaustion.
These are GNU transport-boundary checks, not additional SWI equivalence claims.

`ISO_CA_FILE=/absolute/path/to/ca-bundle.pem` is an optional **process-owner**
setting, inherited by workers. It supplies libcurl's CA file; it is not a public
query option. Without it the platform/libcurl default trust configuration applies.
Peer-chain and hostname verification are explicitly enabled in either case.
The fixture passes the setting only to its disposable test workers.

GNU reports catchable `error(https_certificate_error,Context)`,
`error(https_ca_file_error,Context)` and `error(https_handshake_error,Context)`
for the corresponding libcurl failures. Other transport errors keep their
existing classification. These names are GNU diagnostics, not a portable ISO
error vocabulary or promises about exact SWI messages.

`http_timeout` now also bounds each `src_uri` download. Previously those downloads
always used 30 seconds, ignoring the caller's transport timeout. The deadline
covers the transfer's redirect chain, but is **not** an aggregate budget for
multiple sequential source downloads and the final RPC. The separate query
supervisor deadline still bounds execution overall.


## Source and option-mode follow-up

`rpc_option_cases.py` adds 61 checks: 59 SWI comparisons and two explicit timeout
boundaries. For these comparisons both clients use one disposable GNU target.
The corpus checks first-option precedence, selected variable values, text/list/
predicate source combinations, private source lifetime, promise offsets/templates,
trailing slash URIs and Host:Port. Source-option order is preserved; the SWI
composition accumulator was corrected to agree with its documented order.

An unbound `timeout(T)` is omitted without binding T. The sampled unbound
`once(O)` binds O to true, matching SWI. An unbound `http_timeout(T)` raises an
instantiation error. GNU continues rejecting negative timeout values with
`domain_error(timeout,Value)`; SWI clamps them to zero, with subsequent failures
depending on transport/server behavior. These two cases are boundary assertions,
not SWI matches. The existing 300-second cap and strict option-name policy remain.

Unrecognized options, URI aliases and unusual URI forms, all combinations of
invalid arguments, source-fetch ordering/failures and every transport option still
need further audit. The live SWI deployment is unchanged by the source fix.


Two aliasing checks cover goal capture relative to option normalization. Like SWI,
`rpc/3` captures the goal/template before `once(O)` can bind a shared variable;
`promise/4` captures after normalization. GNU preserves the former using a private
copy for serialization while keeping the original template for local unification.

## URI, validation-order and source-failure audit

`rpc_boundary_cases.py` adds 58 cases: 41 SWI comparisons and 17 explicit
GNU boundaries. URI failure comparisons classify success versus caught error;
they do not require identical HTTP diagnostics. Both clients use the same
loopback GNU target and a disposable HTTP source fixture.

Three corrections follow from the initial eight failing samples:

- Source URLs preserve their trailing slash, percent escapes and query string.
  `/source/` must not silently become `/source`. Only node base URLs have their
  final slash removed before appending `/call`.
- Invalid remote `timeout` values are checked before source composition or I/O.
  Local source-conversion errors precede `http_timeout` validation, matching the
  sampled SWI order. For a source download, GNU checks `http_timeout` before
  starting that transfer, since it also bounds source fetching.
- `http_timeout(none)` raises `type_error(number,none)`. The `none` sentinel
  still applies to remote `timeout` and yield waiting; it is not an HTTP timeout.

The batch records these boundaries without weakening transport policy:

- Unknown options, including HTTP headers, methods, redirect switches and TLS
  verification hooks, raise `domain_error(rpc_option,Option)`. SWI forwards
  non-internal options to its HTTP library. GNU keeps owner-controlled TLS trust.
- GNU rejects timeouts above 300 seconds. This supplements the earlier negative
  timeout checks; fractional and exactly 300-second values are sampled too.
- GNU does not resolve `localhost`, `local` or `self` as implicit node aliases.
  Use an explicit HTTP(S) address or `Host:Port`. GNU also accepts character/code
  lists for addresses, where the sampled SWI client does not.
- GNU appends `/call` to a node path prefix; SWI replaces the path. Query strings
  and fragments in node base addresses remain incompatible; use a base address
  without them. These restrictions do not apply to an exact `src_uri` URL.
- An alphabetic port produces a catchable GNU transport error; the sampled SWI
  client fails silently. Other malformed-address checks compare rejection only.

`rpc_source_tests.py` adds 11 GNU checks, separate from the differential corpus.
404, deadline, oversized-body and embedded-NUL failures stop ordered source
composition before the next fetch or final RPC. For each failure kind, 24 attempts
in one worker exceed the 16-slot transport pool, followed by a successful RPC.
Three further checks assert that invalid deadlines perform no source requests.
Compiled-bundle tests repeat the source failure checks and exercise exact source
URLs and validation ordering. `make rpc-test` includes the new fixture suite.

URI parsing is not exhaustively equivalent: IPv6, userinfo, scheme case, relative
source references and all malformed forms remain unaudited. Exact request-size
edges, aggregate multi-source limits, all validation combinations and TLS
version/cipher/revocation behavior remain open.
