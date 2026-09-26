# ISOBASE deployment threat model

Decision C02, recorded 2026-09-26. Status: current implementation scope and future
release gates. This document defines what must be protected and what is trusted;
it does not certify that every required protection has been implemented.

## Deployment decision

The current implementation targets **one trusted owner, with trusted clients on
one machine, using the authenticated IPv4 loopback listener**. All token holders
belong to the same trust domain. Treat submitted programs and approved fetched
source as owner-authorized code, still subject to the Prolog execution policy.

Only the recorded Apple Silicon macOS comparison environment has local evidence;
see `comparison-lock.json` and COMPARISON_BUILDS.md for exact versions. Linux,
other architectures and other runtime/toolchain combinations are not validated
by that evidence. They need their own platform and containment tests.

| Configuration | Status | Isolation and release condition |
|---|---|---|
| Authenticated local owner node | Current development target | Loopback, owner credential, restricted execution, private query state and bounded resources. Shares the owner's OS identity; no hostile-code containment claim. Must pass the local release gates below before a secure release claim. |
| Explicit `--auth open` | Disposable development/compatibility fixtures only | Every client that can reach the port can execute. Not an authenticated deployment; no sensitive workload or security claim based on this mode. |
| Private-network service, including a tunnel or proxy to loopback | Unsupported future deployment | A private address or loopback backend does not make remote callers trusted. Needs an approved deployment path and the service gates below. |
| Public or mutually untrusted-client service | Unsupported future deployment | Needs OS containment, service-wide hard bounds, authenticated/authorized access as designed, encrypted transport and abuse controls. Separate principals require enforced data/resource ownership. |

A port-forward, tunnel, reverse proxy or credential-sharing wrapper expands the
trust boundary. It does not turn the current local implementation into a supported
network service. No deployment or listener configuration changes accompany C02.

S02 implementation update: owner rules authorize all clients in this trust domain
to use a specific HTTPS RPC credential at an exact endpoint. Token material is
read by the native worker into C memory, not made available as a Prolog value.
This preserves the same-owner threat boundary and does not claim secret isolation
from native exploits or same-user processes. See OUTBOUND_CREDENTIALS.md.

## Actors and trust assumptions

| Actor/input | Trust and expected treatment |
|---|---|
| Owner, host administrator, build operator | Trusted to install binaries, set policy, protect credentials and choose shared data. Root/admin compromise is outside the protection claimed by this node. |
| Processes with the owner's OS privileges | Outside the isolation boundary. They may read credentials or inspect/alter processes and files; bearer authentication is not protection from same-account compromise. |
| Authenticated local clients | Trusted to act as the owner. They are not separate tenants and may access shared clauses and matching continuations. Possessing the token authorizes the full currently exposed query API, including permitted outbound calls. |
| Submitted goals/private source | Authorized by a trusted client, but may contain bugs, runaway computations, malformed terms or accidental forbidden operations. Guards and resource policies must still apply. Deliberately exploitative code is a test input, not a workload for which OS containment is currently promised. |
| Shared source/native bundles | Chosen and approved by the owner; compilation is a trusted build operation. Query clients cannot be allowed to redefine runtime internals or modify the shared database through the restricted API. |
| Fetched `src_uri` programs | Executable source selected by an authorized client. The client must trust its provenance for the local scope. Transport authenticity does not establish that its code is safe. A successful HTTP response is not an approval process. |
| Remote RPC/source peers | Not trusted as parser inputs. Replies, redirects, stalls and certificates must be checked even for approved peers. The local model assumes owner-approved destinations and source provenance; it does not provide safe access to arbitrary hostile services. Application destination policy is enforced; isolated-deployment network controls remain S01. |
| Browser pages and unauthenticated local clients | Untrusted. They must not execute or resume queries, inspect answers or spend query slots without the credential. They can still reach the HTTP parser and consume bounded connection resources. |
| Other OS users | Not intended token holders. File and process isolation depends on the OS account configuration; test credential permissions/ACL assumptions before a release claim. No guarantee against a hostile administrator. |
| Network/DNS/proxies | Transport is not inherently trusted. TLS checking exists for HTTPS; plaintext HTTP has no peer-authenticity or confidentiality promise. Outbound transfers ignore proxy settings, use owner-selected IP pins and deny redirects. |

Trusting a client is not a reason to skip validation. Conversely, validating a
Prolog goal does not make the native runtime safe against an exploit.

## Assets and data policy

1. **Owner credentials and host data.** Keep bearer values out of URLs, submitted
   source, answers, routine logs and outbound requests. Workers currently share
   the owner's OS privileges and environment; a native escape could reach host
   data. Closing that boundary is a service prerequisite.
2. **Shared database and compiled application.** Treat all shared clauses and
   application facts as readable by every authorized client. `clause/2` inspection
   is deliberate functionality. Do not store secrets there that must be hidden
   from a token holder. Obscurity of a compiled bundle is not a confidentiality
   mechanism.
3. **Private query state and answers.** Separate worker/source lifetimes prevent
   accidental cross-query program state. This is not per-client confidentiality:
   all holders of the owner token can resume a matching continuation. Do not
   infer tenant ownership from source-file privacy or a cache key.
4. **Host and node availability.** Execution, output, connection/concurrency and
   sampled memory budgets mitigate runaway work. They do not impose a hard host
   memory ceiling or guarantee availability under local flooding or native abuse.
5. **Peer services and credentials.** Outbound RPC carries goals and possibly
   source to a peer chosen by the client. A peer can see everything sent to it.
   The node must not become a route to unrelated local services or implicitly
   lend a privileged identity to another caller. Application destination policy now requires exact origins and pinned IPs.
   Owner-scoped HTTPS RPC credentials are implemented. Network containment and
   stronger credential isolation are not yet integrated.
6. **Operational records and temporary files.** Source, goals, answers and URLs
   can contain confidential data. Diagnostics and retained artifacts need a
   stated audience, lifetime and cleanup policy. GET requests make URL logging
   especially relevant for any future proxy deployment.

## Boundaries and attack cases

| Boundary / attack | Current controls | Remaining work / evidence required |
|---|---|---|
| Browser/unauthenticated client → query execution | Loopback, owner token, Host/Origin/fetch-metadata checks before admission | S03/S10/S12: broader framing, browser, credential and disclosure review. No execution, continuation access or query eviction on rejection. |
| Client → HTTP parser | Header size/deadline/connection bounds, malformed-header checks, one response per connection | S09/S10/S11: fuzz fragmented, ambiguous, oversized and slow traffic; measure service under admission pressure. |
| Goal/source → restricted evaluator | Predicate policy, indirect-call/DCG guards, source validation | S08/S09: audit every entry point, context and compiled path; malicious inputs must not bypass policy. |
| Query → other queries/shared state | Separate workers/private source, protected shared resolution | K08/K10: verify isolation and replay semantics; S04 adds identity ownership if clients are separated. Shared inspection remains allowed. |
| Worker/native runtime → host | Separate processes and restricted Prolog API, but same owner privileges | S05/S09/S15: native memory safety review and OS containment. A process boundary alone is insufficient against a compromised worker. |
| Outbound URL → local/private/other services | Exact origin/IP grants, socket-bound checks, TLS verification, disabled proxies/redirects and transfer bounds | S01 isolated-deployment network enforcement; S03 credential lifecycle; S14/K05 broader transport audits. Scoped HTTPS credentials are described in OUTBOUND_CREDENTIALS.md. See OUTBOUND_POLICY.md. |
| Remote response/source → term parser/runtime | Body caps, source validation, worker execution limits | S08/S09/K11: hostile replies, deep structures, cycles, malformed Unicode, composed size/time budgets and slot recovery. |
| Runaway query/fan-out → node/host exhaustion | Deadlines, output bounds, sampled query/aggregate memory and admission/eviction | S06/S11/K11/V05: hard service containment, fair budgets and long pressure tests. Sampled overshoot remains possible. |
| Process death → orphan workers/files | Normal shutdown, worker/supervisor cleanup and expiry | S07/V05: controller/supervisor SIGKILL and restart fault injection; no claim of comprehensive abrupt-death cleanup yet. |
| Credential leak/revocation → unauthorized work | Owner-only token file checks; restart reloads token and drops continuations | S03/S12/S16: ACL/core-dump/logging assumptions, rotation and incident procedures; S04 for individual principal revocation. |
| Build/dependency change → policy or runtime compromise | Pinned comparison revisions and observed build fingerprints | S15/V06/V07: trusted build inputs, dependency review, release integrity, provenance and repeatable platform validation. |

These are review obligations, not claims that each unfinished area contains an
exploitable vulnerability. Every future finding should be mapped to an asset,
actor and boundary here, then added to the release checklist.

## Release gates

### Local authenticated release

Before describing the owner-mode node as a secure release within this scope:

- Close all applicable Core security items S01–S03, S07–S10, S12 and S14–S16,
  and the corresponding source/transport/data-lifetime checks. Record whether
  an item is closed or explicitly inapplicable, with reasons and evidence.
- Preserve authentication, browser checks and restricted execution in the tested
  configuration. Open-mode interoperability tests do not count as authentication
  evidence. S02/V04 must establish protected node-to-node interoperability.
- Complete the contract/compatibility gates C03–C04, K01–K11 and V01–V04 for the
  agreed portable scope. Do not call unresolved GNU/SWI disagreements conformity.
- Complete V05–V08 with recorded workload budgets, retained-resource checks,
  supported platform/build evidence and operational instructions. A fresh-machine
  build check and independent security review must be distinguished from local
  developer tests; they have not yet been established.
- State residual assumptions visibly: trusted owner/account, trusted local
  clients, approved source/peers, readable shared data, no per-client isolation,
  no hard host memory guarantee and no protection from host compromise.

This gate is not satisfied merely by accepting the scope decision. Restricting
the present deployment does not remove outbound-policy or parser-hardening work.

### Network or untrusted-workload release

In addition to the applicable local gates:

- Select a supported OS containment design and prove S05–S07 hard resource,
  privilege and process-lifetime boundaries with a deliberately hostile native
  worker, not only restricted Prolog goals.
- Close S11 and S13 for the actual ingress/proxy/TLS topology, including backend
  access, forwarding metadata, admission fairness and recovery under abuse.
- Close S04 whenever principals are to be isolated. Test two-principal query,
  continuation, shared/private-data, credential-use and resource ownership.
  A private network is not a substitute for authorization.
- Enforce outbound restrictions at the appropriate application and OS/network
  boundaries and validate protected interoperability without disabling them.
- Run the complete security, conformance, stress and independent review gates
  against the deployed configuration on every supported platform. Do not infer
  service readiness from the loopback fixture suite.

Private-network and public service implementations are future work, not features
selected for implementation by recording this model. Hardware side-channel and
privileged-host resistance would require a separate scope decision; no such
protection is claimed by this design.

## Relation to the shared contract

This is a deployment decision for the GNU implementation and future joint test
configurations, not a change to ISO Prolog semantics or an audit of the SWI node.
The same claimed security properties must be demonstrated by either deployment;
SWI behavior is not the authority for them. We have not changed the SWI checkout.

Contract 0.1.0 remains unchanged. D07 is **partially scoped**, not resolved:
C02 identifies the supported trust boundary, while identity, outbound policy,
resource and authenticated protocol details still need explicit shared decisions.
Any resulting semantic contract changes follow the versioning policy in
contracts/README.md. Existing gates S01–S16 and K11 remain open as applicable.

## Decision record and maintenance

C02 adopts the already documented single-owner/local assumptions as the explicit
current development scope. It excludes network and mutually untrusted-client
security claims until their gates are met. This is not a reduction of the stated
long-term secure, interoperable ISOBASE objective.

Review this model whenever adding an endpoint, credential mechanism, principal,
source-loading mode, privileged helper, transport feature, proxy topology or
supported platform. Link changed assumptions to implementation tests and contract
versions; never mark an assumption as an implemented control.
