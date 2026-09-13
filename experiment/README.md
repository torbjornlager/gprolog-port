# GNU Prolog C-controller experiment

This directory tests the public C interface, not a complete Web Prolog node.
No GNU Prolog runtime modifications are required for either test.

Run from this directory:

```sh
make test
```

The local installation must be at `../install`. `make` puts its `bin` on
PATH for the compiler subprocesses. Direct runs:

```sh
./controller nested
./controller processes
```

`nested` opens A, obtains its first solution, opens B, obtains both B
solutions and closes B, then resumes A. It verifies the supported query
stack behavior. There is no parameter on `Pl_Query_Next_Solution()` with
which to select A while B is current.

`processes` is a C parent with two children, each exec'ing the same executable
and initializing its own GNU Prolog runtime. Two pipes per child carry
readiness, resume commands and results. Both children enter the foreign
`gate/2` predicate before the parent resumes either. The parent chooses
A1, B1, A2, B2: it finishes A while B is still suspended.

At each gate the native Prolog computation has live environment and choice
point state. A term contains two references to one unbound variable. After
resumption the variable is bound, and C inspects the resulting compound to
verify the actor identity and branch number. Backtracking must produce the
second solution with fresh bindings. A cut on branch 2 must suppress branch
3. A subsequent query must return `PL_EXCEPTION` with the expected term.

The controller validates every expected event and each child exit status.
Alarms bound the C programs to 20 seconds; the Python driver also imposes a
25-second subprocess timeout. `results.json` records all 40 runs.

Limitations: fixed two-child protocol, no general term serialization,
selective receive, arbitrary scheduling, networking, monitors, or resource
limits. It is not a lightweight-process or performance benchmark. Blocking
in a foreign call works here because each child has its own OS process;
it is not suspension of one context within a shared GNU Prolog runtime.
