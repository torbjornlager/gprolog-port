% Fixture extracted from the pinned Trinity example 18.


prove(true, true) :- !.
prove(rpc(URI, A), Proof) :- !,
    prove(rpc(URI, A, []), Proof).
prove(rpc(URI, A, Options), Query@URI/Proof) :- !,
    rpc(URI, prove(A, Query/Proof), [
        src_predicates([prove/2])
      | Options
    ]).
prove((A, B), (ProofA, ProofB)) :- !,
    prove(A, ProofA), prove(B, ProofB).
prove(A, A/Proof) :- clause(A, B), prove(B, Proof).

