% Initial ISOBASE execution policy. Default deny; only pure native predicates
% below, guarded RPC/promise operations and validated source are callable.
% This is not full profile
% conformance and does not provide OS isolation or execution resource limits.
:- dynamic(iso_owned/2).
:- dynamic(iso_shared_dynamic/3).
% Native metadata stays in executable code; snapshot metadata is private.
iso_shared(F,N,I) :- iso_native_shared(F,N,I).
iso_shared(F,N,I) :- iso_shared_dynamic(F,N,I).
:- dynamic(iso_original_clause/2).
:- dynamic(iso_shared_original_clause/2).
iso_shared_clause(H,B) :- iso_native_clause(H,B).
iso_shared_clause(H,B) :- iso_shared_original_clause(H,B).

% Ordinary queries resolve local definitions first, then shared definitions.
% Shared rules keep their own resolution context, including indirect calls.
iso_execute(Goal) :- iso_execute_in(local,Goal).
iso_rewrite(Goal,Safe) :- iso_rewrite_in(local,Goal,Safe).

iso_execute_in(Scope,Goal) :-
    (var(Goal) -> throw(error(instantiation_error,iso_execute/1));true),
    (acyclic_term(Goal) -> true
    ; throw(error(representation_error(cyclic_term),iso_execute/1))),
    iso_rewrite_in(Scope,Goal, Safe), call(Safe).

% Retain native control structure so a source clause's cut keeps its scope.
% A variable in goal position is checked when invoked, after it is instantiated.
iso_rewrite_in(Scope,G, iso_execute_in(Scope,G)) :- var(G), !.
iso_rewrite_in(Scope,(A,B), (SA,SB)) :- !, iso_rewrite_in(Scope,A,SA),iso_rewrite_in(Scope,B,SB).
iso_rewrite_in(Scope,(A;B), (SA;SB)) :- !, iso_rewrite_in(Scope,A,SA),iso_rewrite_in(Scope,B,SB).
iso_rewrite_in(Scope,(A->B), (SA->SB)) :- !, iso_rewrite_in(Scope,A,SA),iso_rewrite_in(Scope,B,SB).
iso_rewrite_in(Scope,once(A), once(SA)) :- !, iso_rewrite_in(Scope,A,SA).
iso_rewrite_in(Scope,\+(A), \+(SA)) :- !, iso_rewrite_in(Scope,A,SA).
iso_rewrite_in(Scope,catch(A,E,B), catch(SA,E,SB)) :- !,
    iso_rewrite_in(Scope,A,SA),iso_rewrite_in(Scope,B,SB).
iso_rewrite_in(Scope,findall(T,G,L), (findall(T,SG,Actual),L=Actual)) :- !, iso_rewrite_in(Scope,G,SG).
iso_rewrite_in(Scope,bagof(T,G,L), iso_bagof_in(Scope,T,G,L)) :- !.
iso_rewrite_in(Scope,setof(T,G,L), iso_setof_in(Scope,T,G,L)) :- !.
iso_rewrite_in(Scope,phrase(B,I), iso_phrase_in(Scope,B,I,[])) :- !.
iso_rewrite_in(Scope,phrase(B,I,O), iso_phrase_in(Scope,B,I,O)) :- !.
iso_rewrite_in(_,throw(E),iso_throw(E)) :- !.
iso_rewrite_in(_,succ(A,B),iso_succ(A,B)) :- !.
iso_rewrite_in(_,between(L,H,N),iso_between(L,H,N)) :- !.
iso_rewrite_in(_,length(L,N),iso_length(L,N)) :- !.
iso_rewrite_in(_,atom_length(A,N),iso_text_length(A,N)) :- !.
iso_rewrite_in(_,atom_codes(A,C),iso_text_codes(A,C)) :- !.
iso_rewrite_in(_,atom_chars(A,C),iso_text_chars(A,C)) :- !.
iso_rewrite_in(_,char_code(A,C),iso_text_char_code(A,C)) :- !.
iso_rewrite_in(_,number_codes(N,C),iso_number_text(N,C,codes)) :- !.
iso_rewrite_in(_,number_chars(N,C),iso_number_text(N,C,chars)) :- !.
iso_rewrite_in(_,atom_concat(A,B,C),iso_text_concat(A,B,C)) :- !.
iso_rewrite_in(_,sub_atom(A,B,L,R,S),iso_text_sub(A,B,L,R,S)) :- !.
iso_rewrite_in(_,term_variables(T,L),(term_variables(T,Actual),L=Actual)) :- !.
iso_rewrite_in(_,sort(L,R),iso_sort(L,R)) :- !.
iso_rewrite_in(_,keysort(L,R),iso_keysort(L,R)) :- !.
iso_rewrite_in(_,T=..L,iso_univ(T,L)) :- !.
iso_rewrite_in(_,arg(N,T,A),iso_arg(N,T,A)) :- !.
iso_rewrite_in(_,is(A,E),(iso_eval(E,V),A=V)) :- !.
iso_rewrite_in(_,G,iso_arithmetic(F,A,B)) :-
    nonvar(G),G=..[F,A,B],member(F,[(=:=),(=\=),(<),(=<),(>),(>=)]),!.
iso_rewrite_in(_,nth0(N,L,E),iso_nth(0,N,L,E)) :- !.
iso_rewrite_in(_,nth1(N,L,E),iso_nth(1,N,L,E)) :- !.
iso_rewrite_in(_,nth0(N,L,E,R),iso_nth_rest(0,N,L,E,R)) :- !.
iso_rewrite_in(_,nth1(N,L,E,R),iso_nth_rest(1,N,L,E,R)) :- !.
iso_rewrite_in(S,call_nth(G,N),iso_call_nth(SG,N)) :- !,iso_rewrite_in(S,G,SG).
iso_rewrite_in(S,time(G),iso_time(SG)) :- !,iso_rewrite_in(S,G,SG).
iso_rewrite_in(_,runtime_property(P),iso_runtime_property(P)) :- !.
iso_rewrite_in(S,rpc(U,G),iso_rpc(S,U,G,[])) :- !.
iso_rewrite_in(S,rpc(U,G,O),iso_rpc(S,U,G,O)) :- !.
iso_rewrite_in(S,promise(U,G,R),iso_promise(S,U,G,R,[])) :- !.
iso_rewrite_in(S,promise(U,G,R,O),iso_promise(S,U,G,R,O)) :- !.
iso_rewrite_in(_,yield(R,M),iso_yield_plain(R,M)) :- !.
iso_rewrite_in(S,yield(R,M,O),iso_yield_result(S,R,M,O)) :- !.
iso_rewrite_in(_,promise_cleanup(R),(iso_integer(R),iso_net_cancel(R))) :- !.
iso_rewrite_in(Scope,clause(H,B), iso_local_clause_in(Scope,H,B)) :- !.
iso_rewrite_in(Scope,G, iso_maplist_in(Scope,C,Lists)) :-
    nonvar(G),functor(G,maplist,N),N>=2,N=<5,!,G=..[maplist,C|Lists].
iso_rewrite_in(Scope,G, iso_foldl_in(Scope,C,Lists,V0,V)) :-
    nonvar(G),functor(G,foldl,N),N>=4,N=<7,!,
    G=..[foldl,C|Args],append(Lists,[V0,V],Args).
iso_rewrite_in(Scope,G, iso_apply_in(Scope,C,Args)) :-
    nonvar(G), functor(G,call,N), N>=1,N=<8, !,
    G=..[call,C|Args].
iso_rewrite_in(Scope,G,Safe) :-
    callable(G), functor(G,F,N),
    (Scope==local,iso_owned(F,N) -> Safe=G
    ; iso_shared(F,N,Internal) -> G=..[_|Args],Safe=..[Internal|Args]
    ; iso_pure(F/N) -> Safe=G), !.
iso_rewrite_in(_Scope,G,_) :-
    (callable(G) -> functor(G,F,N),
        throw(error(permission_error(execute,isobase,F/N),iso_execute/1))
    ; throw(error(type_error(callable,G),iso_execute/1))).

iso_rewrite_quantified_in(Scope,G,SG) :-
    (nonvar(G), G=(V^B) -> SG=(V^SB),iso_rewrite_quantified_in(Scope,B,SB)
    ; iso_rewrite_in(Scope,G,SG)).
iso_bagof_in(Scope,T,G,L) :- iso_rewrite_quantified_in(Scope,G,SG),bagof(T,SG,Actual),L=Actual.
iso_setof_in(Scope,T,G,L) :- iso_rewrite_quantified_in(Scope,G,SG),setof(T,SG,Actual),L=Actual.

iso_apply_in(Scope,C,Args) :-
    (var(C) -> throw(error(instantiation_error,call/1));true),
    (callable(C) -> C=..Parts
    ; (Args=[_|_],atomic(C) -> Type=atom;Type=callable),
      throw(error(type_error(Type,C),call/1))),
    append(Parts,Args,Full), G=..Full, iso_execute_in(Scope,G).

% Separate alternatives preserve relational enumeration for open lists.
iso_maplist_in(_,_,Lists) :- iso_empty_lists(Lists).
iso_maplist_in(Scope,C,Lists) :-
    iso_list_heads(Lists,Heads,Tails),iso_apply_in(Scope,C,Heads),
    iso_maplist_in(Scope,C,Tails).
iso_foldl_in(_,_,Lists,V,V) :- iso_empty_lists(Lists).
iso_foldl_in(Scope,C,Lists,V0,V) :-
    iso_list_heads(Lists,Heads,Tails),append(Heads,[V0,V1],Args),
    iso_apply_in(Scope,C,Args),iso_foldl_in(Scope,C,Tails,V1,V).
iso_empty_lists([]).
iso_empty_lists([[]|Ls]) :- iso_empty_lists(Ls).
iso_list_heads([],[],[]).
iso_list_heads([[H|T]|Ls],[H|Hs],[T|Ts]) :- iso_list_heads(Ls,Hs,Ts).

iso_phrase_in(Scope,B,I,O) :-
    iso_phrase_list(I),iso_phrase_list(O),
    (var(B) -> throw(error(instantiation_error,phrase/3));true),
    iso_expand_dcg((iso_dcg_tmp --> B),(Head :- Body)),
    Head=..[iso_dcg_tmp,I,O], iso_execute_in(Scope,Body).

iso_local_clause_in(Scope,H,B) :-
    (var(H) -> throw(error(instantiation_error,clause/2));true),
    (Scope==local,callable(H),functor(H,F,N),iso_owned(F,N) -> iso_original_clause(H,B)
    ; callable(H),functor(H,F,N),iso_shared(F,N,_) -> iso_shared_clause(H,B)
    ; throw(error(permission_error(access,procedure,H),clause/2))).

iso_pure(true/0).
iso_pure(fail/0).
iso_pure(false/0).
iso_pure(!/0).
iso_pure(repeat/0).
iso_pure(throw/1).
iso_pure((=)/2).
iso_pure(unify_with_occurs_check/2).
iso_pure((\=)/2).
iso_pure(subsumes_term/2).
iso_pure(var/1).
iso_pure(atom/1).
iso_pure(integer/1).
iso_pure(float/1).
iso_pure(atomic/1).
iso_pure(compound/1).
iso_pure(nonvar/1).
iso_pure(number/1).
iso_pure(callable/1).
iso_pure(ground/1).
iso_pure(acyclic_term/1).
iso_pure((@=<)/2).
iso_pure((==)/2).
iso_pure((\==)/2).
iso_pure((@<)/2).
iso_pure((@>)/2).
iso_pure((@>=)/2).
iso_pure(compare/3).
iso_pure(sort/2).
iso_pure(keysort/2).
iso_pure(functor/3).
iso_pure(arg/3).
iso_pure((=..)/2).
iso_pure(copy_term/2).
iso_pure(term_variables/2).
iso_pure((is)/2).
iso_pure((=:=)/2).
iso_pure((=\=)/2).
iso_pure((<)/2).
iso_pure((=<)/2).
iso_pure((>)/2).
iso_pure((>=)/2).
iso_pure(atom_length/2).
iso_pure(atom_concat/3).
iso_pure(sub_atom/5).
iso_pure(atom_chars/2).
iso_pure(atom_codes/2).
iso_pure(char_code/2).
iso_pure(number_chars/2).
iso_pure(number_codes/2).
iso_pure(member/2).
iso_pure(append/3).
iso_pure(length/2).
iso_pure(between/3).
iso_pure(select/3).
iso_pure(succ/2).
iso_pure(nth/3).

% Like phrase/3 in the reference, check the outer list cell, allowing open
% and partial lists. Full traversal would change termination and error timing.
iso_phrase_list(L) :-
    (var(L) -> true; L=[] -> true; L=[_|_] -> true
    ;throw(error(type_error(list,L),phrase/3))).

% Normalize the empty embedded DCG goal, unsupported by GNU's expander.
iso_expand_dcg((Head --> Body),Clause) :-
    iso_dcg_body(Body,Normalized),expand_term((Head --> Normalized),Clause).
iso_dcg_body(B,B) :- var(B),!.
iso_dcg_body({},[]) :- !.
iso_dcg_body((A,B),(X,Y)) :- !,iso_dcg_body(A,X),iso_dcg_body(B,Y).
iso_dcg_body((A;B),(X;Y)) :- !,iso_dcg_body(A,X),iso_dcg_body(B,Y).
iso_dcg_body((A->B),(X->Y)) :- !,iso_dcg_body(A,X),iso_dcg_body(B,Y).
iso_dcg_body(\+(A),\+(X)) :- !,iso_dcg_body(A,X).
iso_dcg_body(B,B) :-
    B=[_|_],!,iso_spine_kind(B,Kind),
    (Kind==proper->true
    ;Kind==cyclic->throw(error(representation_error(cyclic_term),expand_term/2))
    ;iso_throw(error(type_error(list,B),expand_term/2))).
iso_dcg_body(B,B).
