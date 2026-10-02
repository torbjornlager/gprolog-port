# Single-owner credential lifecycle (S03)

Verified on macOS Apple Silicon on 2026-09-30 for the loopback, single trusted
owner model. These controls do not isolate native workers from the owner's
account or authorize public/multi-tenant deployment.

## Provisioning and rotation

1. Use an owner-controlled directory, recommended mode `0700`, outside source
   control. Generate credentials with the exclusive-create `0600` recipe in
   [SECURITY.md](SECURITY.md). It uses 32 random bytes encoded as 64 hex digits
   and refuses to overwrite an existing file or follow an existing symlink.
2. Token and policy files must be regular files owned by the effective user,
   without group/other permission bits or extended ACLs. The descriptor is
   checked after opening with no final symlink following. An ACL causes
   rejection even if it appears restrictive; inspect inherited directory ACLs
   when provisioning. Parent-directory ownership is an operational assumption.
3. To rotate the inbound token, generate a new file with the same procedure in
   the protected directory, then atomically replace the configured token file
   (for example, `os.replace(new_path, token_path)` on the same filesystem).
   Stop and restart the node with that path. Verify that the new token succeeds
   and the old one returns 401. Restart loses all queries and continuations.
4. For immediate inbound revocation, stop the node first. Replacing or deleting
   its file alone does **not** revoke the token held by a running controller.
   Starting with a missing or invalid file fails closed. Provision a fresh token
   before restarting and distribute it through an owner-controlled channel.
5. Outbound RPC reads the selected token file for each admitted transfer. Atomic
   replacement affects subsequent loads; removal makes them fail. Already
   admitted transfers and prefetched results are not retroactively revoked.
   Stop the node to discard that local work, and revoke the old credential at
   the peer. See [OUTBOUND_CREDENTIALS.md](OUTBOUND_CREDENTIALS.md).

Hot inbound rotation and concurrent inbound keys are outside this model.
Never put bearer values in URLs, source, command-line arguments or environment
variables. Trust the selected remote endpoint: it necessarily receives its
credential and could reflect it in a response.

## Process state and diagnostics

The controller, supervisor and worker set both soft and hard `RLIMIT_CORE` to
zero before reading secrets or starting Prolog. Startup fails if this cannot be
done. Linux also requests `PR_SET_DUMPABLE=0`, because a piped core handler can
ignore `RLIMIT_CORE`. The Linux path has not been runtime-verified here.

The controller passes only `LANG`, `LC_ALL`, `LC_CTYPE`, `TZ`, `ISO_CA_FILE` and
`ISO_OUTBOUND_POLICY` to its supervisor. The supervisor sets its own query
offset. Arbitrary ambient secrets, loader configuration and unrelated inherited
descriptors are excluded. macOS uses `POSIX_SPAWN_CLOEXEC_DEFAULT`; glibc 2.34+
uses a close-from spawn action. Other platforms fail query spawning rather than
falling back to unrestricted descriptor inheritance. Standard streams carry
the query protocol; supervisor stderr goes to `/dev/null`.

Inbound temporary token buffers, the stored token on normal exit and consumed
HTTP request buffers are wiped with volatile writes. Outbound owned token and
header buffers are also wiped. Authentication diagnostics omit bearer values;
tests check selected responses and stderr. This is not a guarantee that all
copies in allocators, libraries or transport buffers have been erased.

Zero process core limits are tested directly and across the real
controller → supervisor → worker path. We do not induce crashes or certify
OS-managed diagnostic reports, crash-service uploads, privileged inspection or
same-user debugging. Treat those reports as potentially sensitive and review
their collection and access before deploying. Broader disclosure and deployment
audits remain S12/S16; native containment remains a separate release gate.

## Evidence

`make lifecycle-test` checks exclusive provisioning, symlink refusal, atomic
replacement/deletion while running, restart revocation, missing-file startup
failure, macOS ACL rejection, selected response/stderr redaction, zero core
limits, and real child environment/descriptor isolation. It also checks that
the unprivileged process cannot raise its core limit afterward.

`make test` includes this suite; `make compiled-test` repeats it with a compiled
bundle. Both passed on 2026-09-30, as did the controller ASan/UBSan security and
lifecycle suites. Existing outbound tests still pass all 30 checks, including
protected GNU→GNU, GNU→SWI and SWI→GNU calls. The pinned SWI checkout was tested
from a disposable clean copy at the locked revision; the user's changed checkout
was left untouched. Boundary requirements remain GNU 39/39 and SWI 5/39.
