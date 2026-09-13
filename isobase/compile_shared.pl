% Trusted build-time entry point; use exactly the runtime validator and rewrite.
iso_compile_shared(Input,Output) :-
    op(1150,fx,[dynamic,multifile,discontiguous]),
    open(Input,read,In),
    catch(iso_read_source(In,Terms),Error,(close(In),throw(Error))),close(In),
    iso_prepare_source(Terms,Clauses),
    iso_effective_source(shared,Clauses,Effective),
    iso_register_source(shared,Effective),
    iso_rewrite_source(shared,Effective,Safe),
    findall(pi(F,N,I),iso_shared(F,N,I),PIs),
    open(Output,write,Out),
    catch(iso_write_native(Out,PIs,Safe),Error,(close(Out),throw(Error))),close(Out).
iso_write_native(Out,PIs,Safe) :-
    iso_write_compiled_term(Out,iso_shared_mode(compiled)),
    iso_write_compiled_term(Out,(iso_native_key(A,B):-A=B)),
    (PIs=[] -> iso_write_compiled_term(Out,(iso_native_shared(_,_,_):-fail))
    ;iso_write_native_registry(Out,PIs)),
    findall(iso_native_clause(H,B),iso_shared_original_clause(H,B),Originals),
    (Originals=[] -> iso_write_compiled_term(Out,(iso_native_clause(_,_):-fail))
    ;iso_write_compiled_terms(Out,Originals)),
    iso_write_native_clauses(Out,PIs,Safe).
iso_write_native_registry(_,[]).
iso_write_native_registry(Out,[pi(F,N,I)|Ps]) :-
    iso_write_compiled_term(Out,iso_native_shared(F,N,I)),
    iso_write_native_registry(Out,Ps).
iso_write_native_clauses(_,[],_).
iso_write_native_clauses(Out,[pi(_,N,I)|Ps],Safe) :-
    findall((H:-B),(member(C,Safe),C=(H:-B),functor(H,I,N)),Clauses),
    % Declarations do not make native clauses dynamic. Empty declarations
    % still denote an existing predicate that fails, just as the loader does.
    (Clauses=[] -> functor(H,I,N),iso_write_compiled_term(Out,(H:-fail))
    ;iso_write_compiled_terms(Out,Clauses)),
    iso_write_native_clauses(Out,Ps,Safe).
iso_write_compiled_terms(_,[]).
iso_write_compiled_terms(Out,[C|Cs]) :-
    iso_native_index_safe(C,Native),iso_write_compiled_term(Out,Native),iso_write_compiled_terms(Out,Cs).

% The pinned WAM-to-mini-assembly integer index truncates wide keys to int,
% and the switch sorter subtracts keys in int. Keep wide integer heads out
% of that index; native unification itself supports the full Prolog range.
% A helper prevents the compiler from lifting the unification back into the
% indexed head. Moving the constant to this initial call preserves clause order,
% variable sharing and the original clause's cut scope.
iso_native_index_safe((H:-B),(NH:-(iso_native_key(Key,Value),B))) :-
    H=..[F,Value|Args],integer(Value),(Value < -1000000000;Value > 1000000000),!,
    NH=..[F,Key|Args].
iso_native_index_safe(C,C).
iso_write_compiled_term(Out,T) :-
    iso_write_text(T,[quoted(true),ignore_ops(true)],Text),write(Out,Text),write(Out,'.'),nl(Out).
