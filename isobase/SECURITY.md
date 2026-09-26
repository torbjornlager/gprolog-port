# Local node security

The supported trust model is one node owner and trusted clients on the same
machine. The node binds only IPv4 loopback (`127.0.0.1`). It is not a public
service or a boundary between mutually untrusted tenants.

[THREAT_MODEL.md](THREAT_MODEL.md) records C02: trusted actors and inputs, assets,
attack boundaries, supported deployment scope and the local/service release
gates. The current implementation is a development target; those gates are not
yet all satisfied.

## Start with authentication

Startup requires exactly one of `--auth-token-file FILE` or `--auth open`.
There is no implicit unauthenticated mode. This is a breaking change for older
launch scripts. Compatibility tests and development examples explicitly choose
open mode; Host and browser checks still apply in that mode.

Create a private credential once, from the `isobase` directory:

```sh
python3 - <<'PY'
import os, secrets
with os.fdopen(os.open('owner.token', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
    f.write(secrets.token_hex(32) + '\n')
PY
./isobase-node --auth-token-file owner.token --port 8081
```

Keep this file out of source control. The node requires a regular file owned by
its effective user, with no group or other permission bits, and refuses symlinks.
Its contents must be 32–256 ASCII letters, digits, `_` or `-`, optionally followed
by one LF. Use a randomly generated token; length alone does not ensure strength.
The controller reads it once at startup. Restart with a replacement file to
rotate credentials; all saved continuations disappear on restart.

A client can read the file without putting the token in its process arguments:

```sh
python3 - <<'PY'
from pathlib import Path
from urllib.request import Request, urlopen
request = Request('http://127.0.0.1:8081/call?goal=between(1,5,X)&limit=2',
                  headers={'Authorization': 'Bearer ' + Path('owner.token').read_text().rstrip('\n')})
with urlopen(request) as response:
    print(response.read().decode())
PY
```

The node accepts credentials only in `Authorization: Bearer ...`. Missing or
incorrect credentials return HTTP 401 with a Bearer challenge. Credentials are
not accepted from query strings or cookies. Authentication failures use JSON,
regardless of requested result format. Token contents are compared without an
early exit; tokens are not logged, echoed, or forwarded to worker arguments or
environment variables. Workers still run as the owner and lack OS isolation.

Every query and continuation request is checked before parsing query parameters,
creating source files, admitting a worker, or looking up/evicting a continuation.
All holders of this credential share one trust domain: they can read the shared
database and resume each other's matching continuations. There are no separate
users, roles, or ownership checks within that domain.

## HTTP and browser boundary

Every request must contain exactly one Host naming `127.0.0.1` or `localhost`
with the actual listening port (the port may be omitted only for port 80).
Other hostnames, including DNS names resolving to loopback, are rejected.
When Origin is present it must exactly match `http://` plus the accepted Host
(case-insensitively). Even the two accepted hostnames are different origins;
paths, `null`, other ports and multiple Origin fields are rejected.
When Sec-Fetch-Site is present only `same-origin` and `none` are accepted.
There are no CORS permission headers. CLI clients may omit Origin and
Sec-Fetch-Site; these headers complement authentication, not replace it.

Malformed/folded headers, duplicate security or Content-Length fields,
Transfer-Encoding, nonzero Content-Length, embedded NULs and already-buffered
bytes after the header terminator are rejected. Only GET is supported; the
connection closes after one response. Header reads, connection counts and
response writes retain their existing bounds. Unauthenticated connections can
still consume these bounded HTTP resources; there is no per-client rate limit.

Open mode allows any local client that can reach the port to execute queries.
Browser metadata can be absent or forged by non-browser clients. Use open mode
only for trusted development, not as an authentication substitute.

## Existing protections and remaining work

The Prolog policy allows a restricted set of predicates, guards indirect calls,
validates submitted source, and keeps query state in separate worker processes.
Execution, output, concurrency and sampled memory budgets limit resource use.
HTTPS transport verifies certificates and hostnames; HTTP(S) transfers have
size and time bounds. These controls do not provide full OS containment.

Outbound access now uses a deny-by-default, origin-and-IP policy shared by RPC,
promises and source fetches. Redirects and ambient proxies are disabled; the
actual socket endpoint is checked. See [OUTBOUND_POLICY.md](OUTBOUND_POLICY.md)
for configuration, revocation semantics and evidence.

Remaining boundaries include:

- **Outbound isolation:** application destination enforcement is implemented.
  Network-level restrictions and verification in an isolated deployment remain
  part of S01; scoped HTTPS RPC credentials are implemented under S02.
- **OS isolation:** workers run as the owner. Native-code vulnerabilities and
  same-user processes are outside the protection provided by this token.
- **Hard resource limits:** memory accounting is sampled and can overshoot;
  see MEMORY_LIMITS.md. Local denial of service is still possible.
- **Credential isolation/lifecycle:** [owner-scoped HTTPS RPC credentials](OUTBOUND_CREDENTIALS.md)
  now support protected calls. Native workers still read the selected token file;
  stronger secret isolation and the full S03 lifecycle review remain open.
  Inbound credentials are never automatically forwarded.
- **Deployment:** no public listener, TLS server, reverse-proxy deployment
  contract, multi-user isolation, or comprehensive independent security audit.

## Verification

`make security-test` exercises startup configuration and token-file validation,
authentication, Host/Origin/fetch metadata, malformed headers, restart rotation,
and continuation preservation after rejected requests. `make test` includes
these checks; `make compiled-test` repeats them against a compiled bundle.
For controller memory/undefined-behavior instrumentation:

```sh
make isobase-node-asan
ISO_NODE=./isobase-node-asan python3 security_tests.py
```

Validation on 2026-09-26: local `make test`, compiled bundles, controller
ASan/UBSan security checks, source/HTTPS checks and the 800-page endurance run
passed. The conformance corpus passed 1,276 of 1,277 cases. Its one difference,
also reported by the older RPC/differential suites, is the current SWI reference's
rejection of `limit(0)`. Rebuilding the committed pre-authentication controller
reproduced the RPC failure against SWI; it is not introduced by these controls.
