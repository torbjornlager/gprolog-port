# Secure, interoperable ISOBASE release checklist

Compiled 2026-09-26 from the implementation, saved test results and the local
Trinity reference. This is the consolidated backlog, not a security certification
or a claim that testing can prove the absence of vulnerabilities.

## Compatibility policy

The goal is a shared ISOBASE contract implemented by both GNU Prolog and SWI,
not a GNU implementation that reproduces every SWI behavior. SWI is a comparison
implementation, not the normative authority. GNU behavior is a candidate for the
shared contract too; neither implementation wins a disagreement automatically.

Resolve differences in this order:

1. For behavior covered by the applicable ISO Prolog standard, consult the
   relevant requirement, including permitted implementation-defined choices.
   Record the basis rather than inferring compliance from an implementation's
   reputation or from a differential test.
2. For ISOBASE-specific features such as HTTP, RPC, promises, authentication and
   continuation handling, agree an explicit portable contract. ISO Prolog alone
   does not settle those choices.
3. For extensions and implementation limits, select and document a common
   portable policy or an explicit optional capability. SWI extensions do not
   become mandatory simply because its current node accepts them.
4. Assign the change to GNU, SWI, both implementations, or the contract/tests as
   warranted. Prefer ISO-aligned behavior where applicable, and preserve the
   security requirements in either implementation.

A mismatch is evidence of disagreement, not proof of a GNU defect. Keep
cross-implementation differential tests, but add independently specified contract
expectations so that two implementations sharing a bug cannot establish correctness.
This policy does not authorize changes to the SWI checkout in this documentation task.

## Target and current evidence

The target is the ISOBASE `/call` profile, including its source language,
required predicates, paging, RPC, promises and source transfer. It is not the
whole SWI-Prolog system. Actors, persistent sessions, WebSockets, general I/O and
ISOTOPE are not required merely to deliver ISOBASE.

Reference inspected: Trinity commit
`f237dd5c806893dad17c95cad9a2dc1692a73607` (clean checkout). GNU repository HEAD:
`35bdacd6755595fe9cbd1fe35ba2d1c42c41ad59`, plus the uncommitted owner-authentication
implementation present during this review. Pin both implementation and reference
revisions when producing release evidence.

Already implemented, with regression coverage:

- Restricted Prolog execution policy, indirect-call guards and source validation.
- Separate query workers, private query source and read-only shared-clause access.
- Execution, output, connection and concurrency bounds; sampled query and total
  memory budgets, admission control, eviction and cleanup.
- Loopback binding; explicit authentication configuration; owner bearer token;
  Host, Origin and fetch-metadata checks before query admission.
- Exact origin/IP outbound grants, actual socket checks, certificate/hostname
  verification, disabled proxies/redirects, response sizes and transfer timeouts.
- Interpreted and compiled shared databases, HTTP pagination, RPC and promises.

Latest saved validation: local and compiled suites, controller ASan/UBSan security
checks, source/HTTPS checks and an 800-page endurance run passed. The conformance
corpus passed **1,276/1,277**, but its categories are important: **1,233 reference
comparisons, 42 explicit GNU boundaries and two GNU-only guard tests**. One
reference comparison fails on `limit(0)`. Some reference comparisons check only
rejection or catchability, not exact error semantics. These results do not amount
to 1,276 exact SWI matches. This checklist review did not rerun those suites.

The predicate inventory maps 97 required predicate/arities, but no entry has a
complete mode audit. Existing protections must stay covered while the remaining
work is completed.

## How to use this list

- **Core**: required to make a defensible compatibility/security claim within
  the explicitly selected deployment model.
- **Service**: additionally required when accepting mutually untrusted clients
  or exposing the node beyond the current trusted local environment.
- **Decision**: settle the supported contract first, then implement and test it.
  A documented unsupported feature is not automatically compatible; if the
  portable ISOBASE contract requires it, implementation is necessary.

Check an item only when its stated completion evidence exists. Items marked
“verify” identify incomplete evidence, not a demonstrated vulnerability. The
single-owner token model may remain a valid local product; it must not be
advertised as multi-user isolation.

## 1. Fix the contract and release scope

- [x] **C01 — Core: version the shared contract and pin comparison builds.** Record
  the applicable ISO requirements and agreed ISOBASE choices, then the Trinity/SWI,
  GNU Prolog, compiler, libcurl and supported OS versions. Make the reference
  checkout configurable in every harness instead of relying on personal paths.
  **Done when:** a clean machine can reproduce the same tests and reference
  behavior from recorded revisions.
  **Implemented 2026-09-26:** draft contract 0.1.0, source/runtime/build pins,
  configurable harnesses and per-run provenance; see [COMPARISON_BUILDS.md](COMPARISON_BUILDS.md).
  Seven pinning tests, six independent assertions and local fixtures pass;
  broader comparison remains 1,276/1,277 with D01/K01 unresolved. Validation
  used the recorded local environment; fresh-OS provisioning and release-grade
  reproducible packaging remain S15/V06/V07.
- [x] **C02 — Decision: define the deployment threat model.** State whether
  callers are trusted, whether submitted programs and remote nodes are hostile,
  which data shared clauses may expose, and whether the host account is trusted.
  Choose supported local, private-network and/or public service configurations.
  **Done when:** each claimed configuration has explicit isolation requirements,
  supported platforms and release gates; excluded scenarios are visible.
  **Recorded 2026-09-26:** [THREAT_MODEL.md](THREAT_MODEL.md) defines the current
  authenticated local-owner scope, trust/data assumptions, attack boundaries
  and separate gates for local versus network/untrusted workloads. Only the
  recorded Apple Silicon environment has evidence. This closes the scope
  decision, not the security implementation gates; contract D07 remains partial.
- [x] **C03 — Core: reconcile contract, implementation and documentation.**
  Recheck the 97-predicate inventory against the pinned acceptance matrix, plus
  source directives, expression functors, options and wire behavior. Correct
  stale claims: zero-limit behavior no longer agrees with the current reference;
  an older README section still says redirects are unsupported although bounded
  redirects are implemented. Classify each disagreement against the shared
  contract and assign remediation to GNU, SWI, both, or the documentation/tests.
  **Done when:** every obligation has an implementation/test mapping and there
  is one current status record, with historical audit results labelled as such.
  **Reconciled 2026-09-26:** [STATUS.md](STATUS.md) maps the 97 required
  predicates, optional extension and non-predicate obligations to implementation,
  evidence and open decisions. Drift checks enforce contract/inventory agreement
  and valid evidence links. Stale redirect/auth/zero-limit claims are corrected;
  disagreements and exposed extensions await C04/K01–K11 decisions.
- [x] **C04 — Decision: resolve all 42 host boundaries.** Give each an explicit
  disposition: change GNU, change SWI, change both, establish that the behavior
  is outside the portable contract, or agree an implementation-defined limit or
  optional capability. Record the ISO/ISOBASE rationale. Do not reproduce unsafe
  behavior or require SWI extensions just to make comparisons green.
  **Done when:** no required behavior is exempted by a GNU-specific expected
  result, and any remaining restrictions qualify the compatibility claim.
  **Decided 2026-09-26:** contract [0.2.0](contracts/0.2.0/CONTRACT.md) records all
  42 dispositions: 29 required probes and 13 qualified limits/extensions. Ten
  selected ISO tests supplement them. Required failures remain open implementation
  work; historical GNU-specific outcomes no longer count as conformance passes.

## 2. Complete security boundaries

- [ ] **S01 — Core: owner-controlled outbound destination policy.** Apply one
  policy to RPC, promises and every `src_uri` fetch. Specify permitted schemes,
  hosts, ports and destinations; allow explicitly configured local peers without
  granting access to unrelated local services. Cover IPv4/IPv6, alternate address
  spellings, private/link-local/metadata addresses, DNS changes, redirects and
  proxy environment settings. Bind validation to the actual connection so a
  second resolution cannot bypass it. Disable redirects unless every hop can be
  safely checked. Add network-level restrictions in the isolated deployment.
  **Done when:** allowed peers work and forbidden fixtures receive no request,
  including after redirect/DNS changes and through each transport entry point.
  The application/network layers and redirect hazards are also discussed in
  [OWASP's SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
  **Application enforcement implemented 2026-09-26:** [OUTBOUND_POLICY.md](OUTBOUND_POLICY.md)
  specifies deny-by-default exact-origin/IP grants shared by RPC, promises and
  source downloads, actual socket checks, disabled proxies/redirects, and 62
  integration checks plus sanitized socket-guard checks. Existing local/compiled
  suites pass with explicit fixture grants. **S01 stays open** for network-level
  controls and their verification in an isolated deployment.
- [x] **S02 — Core: authenticated outbound RPC.** Provide owner-configured,
  destination-scoped credentials for GNU-to-GNU and GNU-to-SWI calls; establish
  how SWI callers authenticate to GNU. Keep credentials out of submitted source,
  goals, URLs, results, logs and worker access where the isolation model requires
  it. Do not forward inbound credentials automatically. Authorize *use* of a
  configured remote credential, not just possession of a destination URL.
  Restrict credential forwarding on redirects and forbid remote plaintext bearer
  transport. **Done when:** protected calls work both ways, while hostile source
  or redirects cannot use a more privileged identity or capture its secret.
  **Implemented 2026-09-26 for the current single-owner model:**
  [OUTBOUND_CREDENTIALS.md](OUTBOUND_CREDENTIALS.md) specifies HTTPS origin/path
  grants, private token files, no source/inbound-token forwarding and no redirects.
  Thirty checks verify protected GNU→GNU, GNU→SWI and SWI→GNU calls through
  disposable TLS bridges, including compiled nodes. Credential brokers, hostile
  multi-user isolation and a production TLS deployment remain separate gates.
- [ ] **S03 — Core: finish credential lifecycle verification.** Verify generation,
  provisioning, file permissions/ACL assumptions, rotation, revocation via
  restart, failure behavior and secret redaction. Check crash/core dumps and
  inherited process state. **Done when:** documented operational procedures and
  negative tests demonstrate the chosen single-owner lifecycle. Hot rotation
  and multiple keys are required only if the selected service model needs them.
- [ ] **S04 — Service: principal-aware authorization.** Add identities and
  capabilities where clients must be separated. Bind continuation access,
  cancellation, quotas, source access and privileged outbound credentials to the
  correct principal. Include identity and policy changes in cache reuse rules.
  Shared clauses are intentionally inspectable; define which principals may
  read them. **Done when:** client B cannot resume, inspect, cancel or spend
  client A's resources/credentials without permission; revoked access fails.
- [ ] **S05 — Service: OS-enforced query isolation.** Select and implement a
  supported containment design for the target platform. Separate query execution
  from controller privileges; restrict filesystem, network, process creation and
  accessible descriptors. Minimize environment, working directory and mounts.
  Separate processes running as the same owner are insufficient containment.
  **Done when:** even a deliberately hostile native test worker cannot read
  controller secrets, reach forbidden services or modify host files.
- [ ] **S06 — Service: hard resource containment.** Add OS-enforced memory,
  process/thread, descriptor, CPU and storage bounds as appropriate, for individual
  queries and the service as a whole. Cover startup/source validation and
  transport activity as well as evaluation. Keep sampled budgets for admission
  and useful diagnostics. **Done when:** deliberate overshoot/exhaustion cannot
  destabilize the host or starve the control plane beyond the documented limits.
- [ ] **S07 — Core: abrupt-death and restart cleanup.** Cover controller and
  supervisor SIGKILL, worker crashes, interrupted startup and service restart.
  Establish parent-death/process-group or service-manager containment, and safe
  removal of abandoned private files without deleting another instance's files.
  **Done when:** fault-injection tests leave no runnable orphan workers or
  unbounded sensitive temporary data. Strong containment is a Service gate.
- [ ] **S08 — Core: audit every execution-policy entry point.** Review direct,
  indirect, variable and higher-order goals, DCGs, exceptions, timeout callbacks,
  introspection and source exports. Check compiled and interpreted paths,
  module-qualified calls, name collisions and runtime-internal predicate access.
  **Done when:** adversarial tests cover all routes to execution and demonstrate
  consistent denial of forbidden operations without relying on a reference bug.
- [ ] **S09 — Core: harden parsing and native-code boundaries.** Review and fuzz
  HTTP/header/parameter parsing, percent decoding, UTF-8, Prolog term/source
  readers, answer serialization, worker framing and remote-response parsing.
  Exercise deep nesting, cycles, length arithmetic, truncation and allocation
  failures. Review C/Prolog ownership, transport synchronization and compiler
  workarounds. **Done when:** findings are fixed or explicitly dispositioned,
  minimized regressions are retained and sanitizer/fuzz runs meet recorded goals.
- [ ] **S10 — Core: verify the browser/HTTP boundary under hostile traffic.**
  Extend current Host/Origin/fetch-metadata tests with raw request variants,
  fragmented/coalesced reads, HTTP versions, body/pipeline ambiguity, malformed
  encoding and slow readers/writers. Verify errors never admit queries and
  forwarding headers cannot alter trust. **Done when:** the supported HTTP
  contract is unambiguous across the actual deployment path.
- [ ] **S11 — Service: abuse resistance and fairness.** Add measured global and
  per-principal request/admission controls, connection budgets, bounded queues,
  fair scheduling or rejection, and bounded failed-authentication handling.
  Account for outbound fan-out, source-fetch work and recursive RPC between
  nodes; document the limit of any cross-node budget rather than trusting a
  caller-supplied hop counter. **Done when:** abusive clients cannot monopolize
  workers, continuations or outbound activity at the expense of allowed clients.
- [ ] **S12 — Core: protect source, answers and operational data.** Audit private
  file lifetime/permissions, shared snapshot and compiled-bundle exposure, URL
  query logging, exception messages, stderr and audit logs. Avoid credentials or
  full submitted programs in routine logs. Verify temporary-file races and
  descriptor inheritance. **Done when:** sensitive data reaches only the intended
  owner/client and cleanup/redaction tests cover success and failure paths.
- [ ] **S13 — Service: a supported encrypted deployment path.** Choose direct
  TLS or a documented proxy arrangement. Define external authority/Host and
  Origin handling, trusted forwarding metadata, request limits and backend
  reachability; the current localhost-only Host rules cannot simply be put behind
  an arbitrary proxy. Configure certificate renewal and startup failure behavior.
  **Done when:** the real deployed path passes authentication, browser, framing
  and TLS tests, and the backend cannot bypass those controls.
- [ ] **S14 — Core: TLS and transport policy completion.** Decide supported TLS
  versions/ciphers, trust-store ownership, proxy behavior, HTTPS downgrade rules
  and certificate-revocation requirements. Verify them with local fixtures and
  supported libcurl backends; never expose a caller switch to disable verification.
  **Done when:** policy is explicit and tested, including any stated revocation
  limitation. Existing certificate tests remain regression gates.
- [ ] **S15 — Core: dependency and build security.** Inventory/pin dependencies,
  track vulnerabilities and supported updates, review GNU Prolog/backend patches
  and ARM64 code-generation workarounds, and verify release-bundle provenance and
  integrity. Define which build/source inputs are trusted; compilation should
  not inherit unnecessary owner secrets. **Done when:** reproducible build
  instructions, dependency records and an update/release procedure exist.
- [ ] **S16 — Core: independent security review and operations.** Obtain a review
  of execution policy, C boundaries, authentication, isolation and transport;
  triage findings and retest fixes. Document incident response, key compromise,
  patching, safe shutdown and observable resource failures. Service deployments
  need usable metrics and privacy-preserving audit events.
  **Done when:** no unresolved finding exceeds the release's stated risk policy,
  and operators can detect and recover from the tested failures.

## 3. Close known compatibility differences

- [ ] **K01 — Core: settle the `limit(0)` disagreement.** The current SWI RPC option
  validator raises `type_error(positive_integer,0)`; GNU currently returns failure.
  Check direct HTTP fresh/resumed behavior separately rather than assuming one
  fix covers every layer. This is an ISOBASE API decision, not settled by ISO
  Prolog or by whichever implementation changed most recently. Agree whether
  zero is rejected or has defined semantics, then update the affected GNU/SWI
  client/server validation, errors, tests and documentation to that contract. **Done when:** conformance, RPC and
  differential regressions agree for zero, negative, fractional, missing and
  maximum limits without executing rejected goals.
- [ ] **K02 — Decision: shared numeric contract.** Resolve GNU's signed
  60-bit integer range versus SWI large integers, overflow during parsing versus
  evaluation, rationals and non-finite values where required. Audit shifts,
  powers, rounding, signed zero, underflow, domain errors and evaluation order.
  **Done when:** required values and errors survive local computation and remote
  round trips, or a formally scoped portable numeric boundary is agreed. This
  may require runtime-level work if broader representations are selected;
  restricting the SWI ISOBASE profile to an agreed ISO-permitted numeric policy
  is also a candidate, subject to checking the applicable requirements.
  **GNU progress 2026-09-26:** restored ISO float results for `**/2` and strict
  character/code types in numeric conversions; 32 independent regression cases.
  SWI corrections and the wider numeric audit remain open.
- [ ] **K03 — Decision: shared text and lexical contract.** Resolve SWI strings
  versus GNU double-quoted code lists, non-ASCII double quotes, U+0000, Unicode
  identifiers/digits, escapes, character-code literals and operator syntax.
  Distinguish source reading, number conversion and term writing; fixing one
  does not fix the others. Consider configuring or adapting the SWI ISOBASE
  reader to the agreed ISO-aligned semantics rather than adding SWI string
  objects to GNU solely for parity. **Done when:** required programs and results retain
  the same types, code points and variable identity across hosts.
- [ ] **K04 — Decision: cyclic terms and attributed variables.** Establish which
  semantics the ISOBASE profile requires for unification, occurs checks, copying,
  ordering, all-solutions, errors and wire representation. GNU currently rejects
  some cycles with finite representation errors. **Done when:** required cases
  behave compatibly and unsupported wire structures fail promptly and safely;
  attributed-variable support is not added merely because SWI offers it.
- [ ] **K05 — Core: URI/address contract.** Resolve aliases (`local`, `self`,
  `localhost`), path-prefix handling, queries/fragments, address lists versus
  atoms, scheme case, IPv6, userinfo, malformed ports and relative source URIs.
  Preserve exact source URLs where required. **Done when:** valid common forms
  interoperate and disallowed forms have specified errors without weakening S01.
  **GNU progress 2026-09-26:** queries/fragments and malformed ports now raise
  address domain errors before source downloads or RPC/promise transport. Userinfo
  and malformed authorities are rejected; exact source URLs remain unchanged.
  56 fixture checks cover both APIs, path composition and request-slot recovery,
  including shared snapshot and compiled execution. Broader URI audits and SWI
  implementation changes remain open; S01 destination policy is separate.
- [ ] **K06 — Core: option contract and validation order.** Finish modes for
  duplicate/unknown options, variable values, timeout sentinels, negative and
  excessive timeouts, HTTP options and all source combinations. Decide which
  SWI HTTP options belong in the portable contract and how allowed ones map to
  owner policy. **Done when:** required bindings, errors and ordering match,
  and rejected inputs perform no unintended network requests.
- [ ] **K07 — Core: asynchronous outcome contract.** Specify RPC/promise/yield
  behavior for transport errors, remote exceptions, cancellation, wait timeout,
  message mismatch, repeated yield, cut/backtracking and reference lifetime.
  Preserve safe cleanup instead of reproducing stuck waiters or stale mappings.
  Decide whether GNU `promise_cleanup/1` stays an advertised extension.
  **Done when:** all shared outcomes are tested bidirectionally and intentional
  safety differences are resolved in the portable contract or clearly scoped.
- [ ] **K08 — Core: source loading and shared-database behavior.** Complete
  source declarations, order, composition, exports, shadowing, clause inspection,
  DCG transformation, shared caller context, malformed input and restart tests.
  Verify snapshot and native compilation preserve the same visible semantics.
  **Done when:** the same accepted program produces the same answers and allowed
  introspection, with private state isolated in every loading mode.
- [ ] **K09 — Core: HTTP envelopes and error contract.** Compare both formats,
  statuses, fields, escaping, variable visibility, template sharing, operator
  precedence, exceptional output and exact request/response size edges. Separate
  portable error structure from host-specific diagnostic/context text.
  **Done when:** conforming clients can consume either server's responses and
  all remaining differences are categorized, including authentication failures.
- [ ] **K10 — Core: continuation semantics.** Finish offset replay/cache misses,
  cache-key identity (exact text versus variants), concurrent access, expiry,
  eviction/reinsertion, limit changes, once, disconnect and restart behavior.
  Document repeat execution after a miss and the implications for remote effects.
  Combine this with S04 when identities exist. **Done when:** answer sequences,
  ownership and observable error/replay behavior match the agreed contract.
- [ ] **K11 — Core: aggregate source/transport bounds.** Define exact URL,
  request, response and source size boundaries; number of source parts; total
  assembled source size; and total time across redirects, sequential downloads
  and final RPC. Existing per-transfer deadlines do not themselves provide an
  aggregate download budget. **Done when:** all limits compose predictably,
  fail in the agreed order, and release network slots and workers.

## 4. Finish compatibility evidence and release engineering

- [ ] **V01 — Core: complete a systematic predicate matrix.** For every required
  predicate/arity, enumerate supported instantiation modes, invalid arguments,
  error precedence, success/failure, solution order, determinism, cuts,
  backtracking, aliasing, exceptions and relevant cyclic/partial structures.
  Cover expression functors and directives separately. **Done when:** each row
  has test evidence or an explicit reason a dimension is inapplicable; no row is
  called complete solely because its predicate name appears in a sample.
- [ ] **V02 — Core: finish higher-order/control/DCG coverage.** Cover all closure
  arities, module/context combinations allowed by ISOBASE, malformed and variable
  grammars, nested callbacks, soft-cut syntax if required, negation, cut scope,
  exception propagation and source transfer of transformed code.
  **Done when:** both successful behavior and guard enforcement pass through
  direct, indirect, interpreted, compiled and distributed paths.
- [ ] **V03 — Core: strengthen arithmetic, text and term testing.** Add generated
  and property-based differential cases, round trips, extreme/deep structures,
  sorting stability, grouping, variable sharing and numeric boundary tests.
  Test exact formal errors where required, not only “an error occurred.”
  **Done when:** coverage and remaining exclusions are recorded, and generated
  failures are minimized into stable regressions.
- [ ] **V04 — Core: protected interoperability matrix.** Test GNU→SWI, SWI→GNU
  and GNU→GNU with authentication enabled, both answer formats, source transfer,
  paging, promises, errors and cancellation. Include interpreted/compiled GNU
  bundles and the actual TLS deployment path when supported. Add SWI→SWI
  controls where useful to locate disagreements. Use independent contract
  assertions to distinguish GNU defects, SWI defects and shared defects.
  **Done when:** protected peer configurations work without disabling safeguards.
- [ ] **V05 — Core: long-running stress and recovery.** Run hours-long mixed
  workloads with healthy and hostile queries, connection churn, expiry, atom
  growth, source churn, stalled peers and resource exhaustion. Inject worker,
  supervisor and controller crashes plus restart cycles. Measure memory,
  descriptors, threads, child processes, disk and healthy-client latency.
  **Done when:** quantitative budgets are met and retained-resource growth is
  explained or eliminated; short smoke runs alone do not close this item.
- [ ] **V06 — Core: platform/build matrix.** Validate every claimed OS/architecture,
  GNU/compiler version, libcurl/TLS backend and shared-code mode. In particular,
  the Linux RSS fallback and containment design need actual Linux validation;
  Apple Silicon results do not establish that. State instrumentation coverage:
  current C sanitizer targets do not instrument the full GNU runtime/generated
  Prolog code. **Done when:** each supported combination has repeatable evidence.
- [ ] **V07 — Core: automate release gates.** Add clean-build continuous
  integration for local, security, differential, RPC, source/TLS, compiled and
  conformance suites; scheduled stress/fuzz runs where appropriate. Report
  matches, GNU-only guards, host boundaries, skipped cases and failures separately.
  Capture toolchain/reference versions with results.
  **Done when:** required failures block a release and stale expectations cannot
  silently redefine the target; there are no unexplained required skips.
- [ ] **V08 — Core: publish the supported contract and operations guide.**
  Consolidate installation, secure defaults, peer credentials, allowed outbound
  policy, resource limits, restart/upgrade behavior, error vocabulary, extension
  list and compatibility restrictions. Supply a reproducible two-node protected
  example. **Done when:** a new operator can deploy and verify the claimed
  configuration without relying on this conversation or development open mode.

## Recommended execution order

1. **Agree the contract and resolve the known disagreement:** C01–C04, K01.
   Pin comparison builds for reproducibility; do not freeze SWI behavior as the
   specification. Assign implementation changes according to the agreed semantics.
2. **Secure distributed calls:** S01–S03, K05–K07, K11 and V04. Outbound policy and
   credential use must be designed together, to avoid introducing a privileged
   proxy while adding authenticated RPC.
3. **Build the selected isolation model:** S04–S07, S11 and S13 as required by
   C02, while preserving the local owner mode. Establish hard containment before
   admitting untrusted service workloads.
4. **Implement the shared semantics on both nodes:** K02–K04, K08–K10 and V01–V03. Settle numeric,
   text and cyclic-term architecture early; these can dominate the remaining work.
5. **Close security and release evidence:** S08–S10, S12, S14–S16 and V05–V08.
   Fuzzing, code review and regression tests should also run throughout earlier
   stages, rather than waiting until implementation ends.

A trusted local release may exclude Service items only by explicitly retaining
that narrow trust model. A service for untrusted users must close the applicable
Service items too. An interoperable ISOBASE claim requires both nodes to satisfy
the shared contract; unresolved differences in required semantics cannot be
counted as “passing boundaries.” Agreement may involve moving SWI closer to GNU,
not extending GNU to match every feature of the general SWI runtime.

## Evidence links

- [Current security boundary](SECURITY.md)
- [Conformance ledger](CONFORMANCE.md)
- [Required predicates](PREDICATE_CHECKLIST.md)
- [Text/numeric differences](TEXT_NUMERIC_BOUNDARY.md)
- [RPC/source/transport differences](RPC_BOUNDARY.md)
- [Resource policies and measurements](MEMORY_LIMITS.md)
- [Pinned reference acceptance matrix](../../trinity-demonstrator/docs/WEB_PROLOG_BUILTINS_ACCEPTANCE_MATRIX.md)

This list consolidates known work and the remaining verification programme.
New findings from those audits become additional release blockers; “complete
list” does not mean there can be no undiscovered defects.
