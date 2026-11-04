# Optional Linux query jail

The default native launcher remains private/trusted development. A public
presenter must opt into `--query-jail`, `--lease-dir`, and `--parent-fd`, use
an owner-only controller token, and enforce the deployment boundary separately.
No public mode silently falls back to an uncontained worker.

The trusted controller starts with only KILL, SETGID, SETUID and SYS_CHROOT.
Before parsing source, each supervisor chroots into an immutable worker/library
tree, clears supplementary groups, switches to a distinct UID/GID in
20000–60000, clears capabilities, disables dumps, and installs no-new-privileges
and seccomp. There is no procfs, writable directory or controller credential in
that tree. Submitted source and public shared definitions arrive on read-only
FDs 3/4; other inherited descriptors are closed. Each process has 64 FDs,
32 processes/threads per UID, zero core/file output, and a 2 GiB address-space
ceiling (GNU reserves roughly 1.1 GiB of sparse BSS before allocating stacks).
Resident-memory limits are enforced separately by the root controller and the
container cgroup.

Workers can create only Unix sockets. An authenticated peer-credential broker
at the Linux abstract address `trinity-n6-egress` must validate outbound URLs,
TLS, quotas and deadlines. Direct IP/packet/netlink sockets, io_uring, namespace
changes, ptrace, process_vm, privilege changes and process-group escape are
blocked. The broker is provided by the demonstrator deployment, not this core.

A fresh process group is established atomically at spawn. The controller is a
child subreaper and kills/reaps the complete group on completion, cancellation,
expiry, or presenter lifetime-pipe EOF. Resident-memory sampling includes all
group members, including adopted children and threads that fork descendants.

This is containment within a shared kernel, not a VM or a guarantee against
kernel vulnerabilities or denial of service. The container needs its own hard
memory, CPU and process limits and a read-only root. A malicious allocation
burst can still restart that bounded service before sampled limits intervene.
