# Owner-controlled outbound access

GNU ISOBASE now denies outbound access unless the owner explicitly grants it.
The same policy applies to RPC, promises and every `src_uri` transfer, including
compiled nodes. Inbound authentication does not grant a destination automatically;
`--auth open` does not disable outbound checks.

## Configuration

Create an owner-only regular file (recommended permissions `0600`). Each record
contains four whitespace-separated fields: **scheme host port pinned-IP**.
An optional `rpc ENDPOINT TOKEN_FILE` suffix authorizes a scoped HTTPS bearer
credential; see [OUTBOUND_CREDENTIALS.md](OUTBOUND_CREDENTIALS.md).
Blank lines and lines beginning with `#` are allowed. No wildcards or port ranges
are supported; use one unique record per origin. Scheme is `http` or `https`;
ports are decimal 1–65535. Hostnames are case-insensitive, and numeric rule hosts
must use libcurl's canonical spelling. IPv6 origin hosts use brackets; IP pins
use bare numeric addresses. Scoped/mapped IPv6 addresses are unsupported.

Example owner configuration, replacing the example origin and IP with your peer:

```text
# Disposable local peer, at precisely this port
http 127.0.0.1 8082 127.0.0.1
# Remote peer: certificate identity remains peer.example
https peer.example 443 192.0.2.10
# Explicit IPv6 local peer
http [::1] 8083 ::1
```

Start with the policy file:

```sh
./isobase-node --auth-token-file /absolute/path/owner.token \
  --outbound-policy /absolute/path/outbound.policy
```

`ISO_OUTBOUND_POLICY=/absolute/path/outbound.policy` is equivalent and also
applies to direct workers; the controller flag takes precedence. Without a file,
or with an empty policy, transfers raise `error(outbound_denied,_)`. Missing,
unsafe or malformed configured files raise `error(outbound_policy_invalid,_)`.
Validation happens when a transfer is requested, not at controller startup.
Policy files must belong to the effective owner, have no group/other permissions,
be regular files, not symlinks, and fit within 64 KiB with lines below 1024 bytes.
A duplicate matching origin is rejected rather than picking an arbitrary rule.

The owner must explicitly approve local, private and link-local destinations;
none receive an implicit exception. Approval grants access to every path on the
specified origin. Optional credential grants additionally restrict the RPC
endpoint; neither form approves source contents.
Query options cannot add grants or choose another policy file.

## Connection enforcement

Before allocating a request slot or starting its network thread, the transport
parses the URL, rejects userinfo and scoped addresses, finds its exact origin,
and copies the owner's IP pin into the request. Hostname targets use that numeric
pin; there is no DNS lookup or secondary resolution to change the destination.
The socket callback also checks the actual address family, IP and port before
opening a socket. Alternate numeric URL spellings may normalize to an approved
origin, but cannot grant a different IP or port.

The pin changes the connection endpoint, while the original hostname remains
the HTTP Host and TLS certificate/SNI identity. HTTPS certificate checking stays
enabled. Proxy and pre-proxy settings are explicitly disabled, including ambient
proxy environment variables. Each transfer has a fresh libcurl handle.

**All redirects are disabled**, including redirects to another allowed origin
and same-origin redirects. A 3xx response produces `http_redirect_denied`; use the
final approved URL. This deliberately replaces the earlier five-hop behavior.
Source URLs still preserve their exact path and query string.

Each new transfer rereads the policy. Replace it atomically to change grants.
An already admitted transfer keeps its copied pin, and paging may have prefetched
an answer before revocation. Revocation prevents new transfers; it does not
cancel existing transfers or erase buffered answers. Restart/terminate queries
when immediate cancellation is required. IP changes require owner policy updates;
there is no automatic DNS-based failover.

## Verification and remaining deployment work

`make outbound-test` runs 62 integration checks with forbidden destination and
proxy fixtures receiving zero requests, plus a sanitized C test of the actual
socket guard against changed IPs, ports, families and IPv6 scopes. Integration
checks exercise RPC, promises, source downloads, IPv4/IPv6, alternate numeric
forms, redirects, policy errors, revocation and controller configuration.
`make compiled-test` repeats the policy integration tests against compiled workers.
Existing HTTPS, source, address, local and compiled suites are also retained.
Tests grant only their dynamically allocated fixture origins via
`outbound_test_policy.py`; that helper never modifies the owner's policy file.

This completes the application enforcement part of S01 for the current local
owner model. S01 remains open for network-level enforcement and verification in
an isolated deployment. Workers still share the owner's OS identity; this policy
is not containment against native compromise. Owner-scoped HTTPS RPC credentials are now implemented for the single-owner
model; see OUTBOUND_CREDENTIALS.md. No firewall or host network configuration is changed by this patch.

Design references: [libcurl connection pinning](https://curl.se/libcurl/c/CURLOPT_CONNECT_TO.html),
[the socket callback](https://curl.se/libcurl/c/CURLOPT_OPENSOCKETFUNCTION.html) and
[OWASP SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
