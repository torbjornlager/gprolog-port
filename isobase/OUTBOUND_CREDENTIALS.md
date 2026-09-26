# Owner-scoped outbound RPC credentials

An owner may now attach a bearer credential to one approved **HTTPS origin and
exact RPC endpoint**. Existing four-field outbound rules remain anonymous. Add
three fields to a rule to authorize credential use:

```text
https peer.example 443 192.0.2.10 rpc /call /absolute/path/peer.token
https other.example 443 192.0.2.20 rpc /nested/call /absolute/path/other.token
```

The owner selects the peer, IP pin, endpoint and token file. Query callers cannot
provide tokens, select token files or override the Authorization header through
RPC options. The authorization applies to every authorized local client in the
current single-owner model. It does not distinguish mutually untrusted users.

Use the existing `--outbound-policy FILE` setting; see
[OUTBOUND_POLICY.md](OUTBOUND_POLICY.md). The optional fields must be exactly
`rpc ENDPOINT ABSOLUTE_TOKEN_FILE`. Endpoint paths contain only ASCII letters,
digits, slash, underscore and hyphen. Paths are case-sensitive and compared to
the parsed request path; encoded policy paths and relative token paths are not
accepted. Paths with spaces are not supported in this whitespace-separated file.

Token files must be owner-only regular files belonging to the effective user,
not symlinks. Use `0600` permissions. Contents are 32–256 ASCII letters, digits,
underscores or hyphens, optionally followed by one newline. This includes the
GNU owner-token format and the pinned SWI node's issued bearer-token format.
Provision tokens privately through the peer's owner interface. Never paste them
into submitted goals, source, URLs, command arguments, or version control.

## Scope and failure behavior

- Only RPC and promise transfers to the configured endpoint receive a header.
  A different RPC path on a credential-bearing origin is rejected with
  `outbound_credential_scope`, before any request.
- `src_uri` downloads receive **no RPC credential**, even on the same origin.
  Authenticated source fetching is not part of this feature.
- Inbound client credentials are never reused for outgoing requests. A request
  without an owner credential rule remains anonymous, even if its caller was
  authenticated locally.
- Credential rules for HTTP are invalid, including loopback HTTP. Bearer-bearing
  client traffic requires TLS with certificate and hostname verification.
- Redirects remain disabled. Credentials cannot be forwarded to another path,
  host, port or scheme through a redirect. Proxy environment variables remain
  disabled, and the actual socket endpoint must match the owner's IP pin.
- Missing, unsafe, malformed or unreadable token files produce the generic
  `outbound_credential_invalid` error. Diagnostics do not include the token or
  its filename. Authentication failures from a peer retain that peer's existing
  HTTP/Prolog error behavior.

Each admitted transfer reads the current token file. Use atomic replacement for
rotation; removal makes subsequent credential loads fail. Already admitted or
completed transfers and prefetched answers are not retroactively revoked.
Revoking a peer-side token remains the peer owner's responsibility. Full crash,
ACL and credential-lifecycle verification remains S03.

The bearer header is constructed in the C transport, not in Prolog terms or URL
parameters. Temporary buffers and the owned header list are wiped after use.
The remote peer necessarily receives the token; approve trustworthy endpoints.
A malicious peer can reflect information in its response, so endpoint trust is
not replaced by automatic response redaction.

## SWI interoperability

The pinned SWI node accepts issued bearer tokens. The owner can grant an
appropriate token on that node and put its value in the configured private file.
GNU then sends the same standard Authorization header used by SWI's own clients.

A trusted SWI client can read a GNU token from a private file and call its TLS
endpoint with `request_header('Authorization'=Header)` and a verified CA setting.
Do this in owner-controlled client code, not by embedding a secret in a remotely
submitted goal. The test uses `cacert_file(CAFile)` and leaves certificate
verification enabled. A SWI node that accepts arbitrary caller HTTP options does
not thereby have GNU's owner-scoped outbound credential policy.

`make credentials-test` runs 30 checks against the pinned runtimes. It verifies
protected GNU→GNU, GNU→SWI and SWI→GNU calls, promise delivery, path scoping,
source isolation, no inbound-token forwarding, redirect blocking, plaintext
rejection, file failures, token replacement, cleanup and diagnostic hygiene.
The compiled suite repeats these checks using compiled GNU workers and nodes.
Sanitized C checks cover token length, injection rejection and explicit buffer
wiping alongside the socket guard tests.

Tests use temporary CAs and TLS bridges to protected loopback backends because
the GNU listener currently serves HTTP only. These are disposable fixtures,
not a supported production reverse-proxy deployment. No real credentials or
external services are used and the pinned SWI checkout remains unchanged.

## Isolation limit

This completes S02 for the current trusted single-owner model. Native workers
still share the owner's OS identity and read credential files into C memory;
libcurl also handles the header. No guarantee is made against native compromise,
crash dumps or same-user processes. Moving secrets to a separate credential
broker is part of any future stronger isolation design, alongside S01/S05 and
principal-aware authorization. It is not implemented by this patch.

Transport handling follows [libcurl's header ownership and security rules](https://curl.se/libcurl/c/CURLOPT_HTTPHEADER.html).
