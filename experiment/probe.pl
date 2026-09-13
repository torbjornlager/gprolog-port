:- foreign(gate(+atom, +integer)).

choice(1).
choice(2).
choice(3).

% The environment, outer choice point and an aliased variable are live at
% gate/2. Cut on the second solution must suppress choice(3).
worker(Id, N, Result) :-
    choice(N),
    Pair = pair(X, X),
    var(X),
    gate(Id, N),
    X = value(Id, N),
    Pair = pair(Result, Result),
    (N = 2 -> ! ; true).

throws :- throw(probe_exception).
