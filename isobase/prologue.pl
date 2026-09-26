% Profile prologue: internal wrappers are called only through the policy.
iso_nth(Base,N,List,Element) :-
    (var(N) -> iso_nth_enum(Base,N,List,Element)
    ;iso_list_integer(N),Index is N-Base,Index>=0,iso_nth_at(Index,List,Element)).
iso_nth_enum(I,I,[E|_],E).
iso_nth_enum(I,N,[_|Tail],E) :- J is I+1,iso_nth_enum(J,N,Tail,E).
iso_nth_at(0,[E|_],E) :- !.
iso_nth_at(N,[_|Tail],E) :- N>0,M is N-1,iso_nth_at(M,Tail,E).
iso_nth_rest(Base,N,List,E,Rest) :-
    (var(N) -> iso_nth_rest_enum(Base,N,List,E,Rest)
    ;(integer(N),N>=Base -> Index is N-Base,iso_nth_rest_at(Index,List,E,Rest)
     ;(Base=0->Type=nonneg;Type=positive_integer),
      iso_throw(error(type_error(Type,N),nth/4)))).
iso_nth_rest_enum(I,I,[E|Rest],E,Rest).
iso_nth_rest_enum(I,N,[H|Tail],E,[H|Rest]) :-
    J is I+1,iso_nth_rest_enum(J,N,Tail,E,Rest).
iso_nth_rest_at(0,[E|Rest],E,Rest) :- !.
iso_nth_rest_at(N,[H|Tail],E,[H|Rest]) :-
    N>0,M is N-1,iso_nth_rest_at(M,Tail,E,Rest).

% A private counter survives backtracking within this call only. No global
% registry and no restarting Goal to find its Nth solution.
iso_call_nth(Goal,N) :-
    (var(N) -> Counter=count(0),call(Goal),
        arg(1,Counter,Previous),N is Previous+1,nb_setarg(1,Counter,N)
    ;iso_integer(N),
     (N>0 -> once((iso_call_nth(Goal,K),K=:=N))
     ;throw(error(domain_error(not_less_than_one,N),call_nth/2)))).

% /call does not expose the demonstrator's terminal timing output events.
% Keep answer, failure and exception behavior; report CPU timing on diagnostics.
iso_time(Goal) :-
    statistics(runtime,[Start|_]),
    catch(call(Goal),Error,(iso_time_report(Start),throw(Error))),
    iso_time_report(Start).
iso_time_report(Start) :-
    statistics(runtime,[End|_]),Elapsed is End-Start,
    format(user_error,'% CPU time: ~d ms~n',[Elapsed]).

% These describe this query runtime, not persistent application storage.
iso_runtime_property(implementation(gnu_native)).
iso_runtime_property(persistent(false)).
iso_runtime_property(inbound_addressable(false)).
iso_runtime_property(dom(false)).
iso_runtime_property(actor_isolation(os_process)).
iso_runtime_property(hard_termination(true)).

% SWI's visible arg/3 also enumerates argument positions when N is free.
iso_arg(N,T,A) :-
    (var(T)->throw(error(instantiation_error,arg/3))
    ;compound(T)->true;iso_throw(error(type_error(compound,T),arg/3))),
    (var(N)->functor(T,_,Arity),between(1,Arity,N),arg(N,T,A)
    ;arg(N,T,A)).

% Reconcile common arithmetic behavior without widening GNU's integer range.
iso_eval(E,V) :-
    (compound(E) -> E=..[F|Args],iso_eval_args(Args,Values),iso_eval_function(F,Values,V)
    ;V is E).
iso_eval_args([],[]).
iso_eval_args([E|Es],[V|Vs]) :- iso_eval_args(Es,Vs),iso_eval(E,V).
iso_eval_function(F,[I],I) :- integer(I),member(F,[floor,ceiling,truncate,round,float_integer_part]),!.
iso_eval_function(float_fractional_part,[I],0) :- integer(I),!.
iso_eval_function(round,[A],V) :- !,
    T is truncate(A),D is A-T,
    (D>=0.5->V is T+1;D =< -0.5->V is T-1;V=T).
iso_eval_function(F,[A,B],_) :- member(F,[^,**]),A=:=0,B<0,!,
    throw(error(evaluation_error(zero_divisor),(is)/2)).
iso_eval_function(atan2,[A,B],V) :- A=:=0,B=:=0,!,iso_atan2_zero(A,B,V).
% ** retains GNU's ISO float result, including integer operands (contract B04).
iso_eval_function(^,[A,B],V) :- integer(B),B<0,!,V is float(A)^B.
iso_eval_function(log,[A],_) :- A=:=0,!,throw(error(evaluation_error(float_overflow),(is)/2)).
iso_eval_function(F,Args,V) :- E=..[F|Args],V is E.
iso_arithmetic(F,A,B) :- iso_eval(A,X),iso_eval(B,Y),G=..[F,X,Y],call(G).

iso_length(L,N) :-
    (var(N)->true;iso_integer(N),
      (N>=0->true;throw(error(domain_error(not_less_than_zero,N),length/2)))),
    iso_spine_kind(L,Kind),
    (Kind==cyclic->throw(error(representation_error(cyclic_term),length/2))
    ;Kind==improper->iso_throw(error(type_error(list,L),length/2))
    ;Kind==open,var(N)->iso_spine_tail(L,Tail),Tail\==N,length(L,N)
    ;length(L,N)).

% Cell-identity detection follows only tails, ignoring cycles in elements.
:- foreign(iso_native_spine_kind(term,term)).
iso_spine_kind(L,Kind) :- iso_native_spine_kind(L,Kind).
iso_spine_tail(L,Tail) :- (var(L)->Tail=L;L=[_|Rest],iso_spine_tail(Rest,Tail)).
% GNU cannot safely copy a cyclic exception ball into its exception store.
iso_throw(E) :-
    (acyclic_term(E)->throw(E)
    ;throw(error(representation_error(cyclic_term),throw/1))).

% SWI succ/2 checks the first nonvariable argument and unifies the other.
% Validate before entering native code so cyclic error culprits stay finite.
iso_succ(A,B) :-
    (nonvar(A)->iso_natural(A),succ(A,Next),B=Next
    ;iso_natural(B),succ(A,B)).
iso_natural(N) :-
    iso_list_integer(N),
    (N>=0->true;iso_throw(error(domain_error(not_less_than_zero,N),succ/2))).
iso_list_integer(N) :-
    (integer(N)->true
    ;var(N)->throw(error(instantiation_error,integer_relation))
    ;iso_throw(error(type_error(integer,N),integer_relation))).

% Infinite upper bounds enumerate lazily within the native integer range.
iso_between(L,H,N) :-
    iso_list_integer(L),
    (H==inf->iso_between_unbounded(L,N)
    ;H==infinite->iso_between_unbounded(L,N)
    ;iso_list_integer(H),(var(N)->true;iso_list_integer(N)),between(L,H,N)).
iso_between_unbounded(L,N) :-
    (var(N)->iso_between_from(L,N)
    ;iso_list_integer(N),N>=L).
iso_between_from(L,L).
iso_between_from(L,N) :-
    (L=:=1152921504606846975->throw(error(evaluation_error(int_overflow),between/3))
    ;Next is L+1,iso_between_from(Next,N)).

% Compute result lists independently; output arguments are unified afterwards.
iso_sort(L,R) :- sort(L,Actual),R=Actual.
iso_keysort(L,R) :-
    iso_spine_kind(L,Kind),
    (Kind==open->throw(error(instantiation_error,keysort/2))
    ;Kind==improper->iso_throw(error(type_error(list,L),keysort/2))
    ;Kind==cyclic->throw(error(representation_error(cyclic_term),keysort/2))
    ;true),keysort(L,Actual),R=Actual.
iso_univ(T,L) :-
    (var(T)->T=..L
    ;T=..Actual,iso_univ_output(Actual,L)).
% SWI checks the remaining list tail only after matching the preceding head.
iso_univ_output(Actual,L) :-
    (var(L)->L=Actual
    ;L=[]->Actual=[]
    ;L=[H|Tail]->Actual=[A|Rest],A=H,iso_univ_output(Rest,Tail)
    ;iso_throw(error(type_error(list,L),(=..)/2))).

:- foreign(iso_atan2_zero(term,term,term)).
