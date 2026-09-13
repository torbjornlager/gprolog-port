% Source loading for the private ISOBASE query worker. This validates source
% structure, protects existing definitions, and rewrites bodies through the
% execution policy. The worker process owns all loaded source.
iso_load_source(File) :- iso_load_file(local,File).
iso_load_shared(File) :- iso_load_file(shared,File).

iso_load_file(Scope,File) :-
    op(1150, fx, [dynamic,multifile,discontiguous]),
    open(File, read, Stream),
    catch(iso_read_source(Stream, Terms), Error,
          (close(Stream), throw(Error))),
    close(Stream),
    iso_prepare_source(Terms, Clauses),
    iso_effective_source(Scope,Clauses,Effective),
    iso_register_source(Scope,Effective),
    iso_rewrite_source(Scope,Effective, Safe),
    iso_install_source(Safe).

% Match the demonstrator's restoration of shared imports: declarations alone
% do not shadow a shared definition. At least one local clause is required.
iso_effective_source(shared,Clauses,Clauses).
iso_effective_source(local,Clauses,Effective) :-
    iso_filter_declarations(Clauses,Clauses,Effective).
iso_filter_declarations([],_,[]).
iso_filter_declarations([C|Cs],All,Effective) :-
    (C=iso_declare(F,N),iso_shared(F,N,_),\+iso_defines(All,F,N) -> Effective=Rest
    ; Effective=[C|Rest]),
    iso_filter_declarations(Cs,All,Rest).
iso_defines([C|_],F,N) :-
    C\=iso_declare(_,_), (C=(H :- _) -> true;H=C),
    functor(H,F,N),!.
iso_defines([_|Cs],F,N) :- iso_defines(Cs,F,N).

iso_register_source(_,[]).
iso_register_source(Scope,[C|Cs]) :-
    (C=iso_declare(F,N) -> true
    ; (C=(H :- _) -> true; H=C),functor(H,F,N)),
    (Scope==shared ->
        (iso_shared(F,N,_) -> true
        ; atom_concat('$shared$',F,Internal),assertz(iso_shared_dynamic(F,N,Internal)))
    ; (iso_owned(F,N) -> true;assertz(iso_owned(F,N)))),
    iso_register_source(Scope,Cs).
iso_rewrite_source(_,[],[]).
iso_rewrite_source(Scope,[C|Cs],[S|Ss]) :-
    (C=iso_declare(F,N) ->
        (Scope==shared -> iso_shared(F,N,Internal);Internal=F),
        S=iso_declare(Internal,N)
    ; (C=(H :- B) -> true; H=C,B=true),
      iso_rewrite_in(Scope,B,SB),
      (Scope==shared ->
          assertz(iso_shared_original_clause(H,B)),
          functor(H,F,N),iso_shared(F,N,Internal),H=..[_|Args],SH=..[Internal|Args]
      ; SH=H,assertz(iso_original_clause(H,B))),
      S=(SH :- SB)),
    iso_rewrite_source(Scope,Cs,Ss).

iso_read_source(Stream, Terms) :-
    read_term(Stream, Term, [syntax_error(error)]),
    (Term == end_of_file -> Terms=[]
    ; Terms=[Term|Rest], iso_read_source(Stream, Rest)).

% Validate everything before installing anything. In particular, loading
% source never executes initialization/1, arbitrary directives or user hooks.
iso_prepare_source([], []).
iso_prepare_source([Term|Terms], Clauses) :-
    (nonvar(Term), Term=(:- Directive) ->
        iso_declaration(Directive, Declarations), append(Declarations,Rest,Clauses)
    ; nonvar(Term), Term=(_ --> _) ->
        iso_expand_dcg(Term, Clause), iso_source_clause(Clause),
        Clauses=[Clause|Rest]
    ; iso_source_clause(Term), Clauses=[Term|Rest]),
    iso_prepare_source(Terms, Rest).

iso_declaration(Directive, Declarations) :-
    (nonvar(Directive),
     (Directive=dynamic(Spec);Directive=multifile(Spec);Directive=discontiguous(Spec)) ->
        iso_predicate_specs(Spec, Declarations)
    ; throw(error(permission_error(load, directive, Directive), iso_load_source/1))).
iso_predicate_specs(Spec, Declarations) :-
    (nonvar(Spec), Spec=(A,B) ->
        iso_predicate_specs(A,Left),iso_predicate_specs(B,Right),append(Left,Right,Declarations)
    ; nonvar(Spec), Spec=Name/Arity, atom(Name), integer(Arity), Arity>=0 ->
        current_prolog_flag(max_arity, Max),
        (Arity=<Max -> true
        ; throw(error(representation_error(max_arity),iso_load_source/1))),
        iso_source_name(Name, Arity), Declarations=[iso_declare(Name,Arity)]
    ; throw(error(type_error(predicate_indicator,Spec),iso_load_source/1))).

iso_source_clause(Clause) :-
    (nonvar(Clause), Clause=(Head :- _) -> true; Head=Clause),
    (callable(Head) -> true
    ; throw(error(type_error(callable,Head),iso_load_source/1))),
    functor(Head, Name, Arity),
    iso_source_name(Name, Arity).
iso_source_name(Name, Arity) :-
    (sub_atom(Name,0,4,_,iso_);sub_atom(Name,0,1,_,'$');
     Name=term_expansion;Name=goal_expansion;
     iso_rpc_reserved(Name,Arity);
     Name=(:-);Name=(?-);Name=(:);
     current_predicate(Name/Arity)) ->
        throw(error(permission_error(redefine,procedure,Name/Arity),iso_load_source/1))
    ; true.

iso_install_source([]).
iso_install_source([iso_declare(Name,Arity)|Clauses]) :- !,
    (current_predicate(Name/Arity) -> true
    ; functor(Head,Name,Arity), assertz((Head :- fail)), retractall(Head)),
    iso_install_source(Clauses).
iso_install_source([Clause|Clauses]) :-
    assertz(Clause), iso_install_source(Clauses).

% Public wrappers must not be shadowed by source definitions.
iso_rpc_reserved(rpc,2).
iso_rpc_reserved(rpc,3).
iso_rpc_reserved(promise,3).
iso_rpc_reserved(promise,4).
iso_rpc_reserved(yield,2).
iso_rpc_reserved(yield,3).
iso_rpc_reserved(promise_cleanup,1).

iso_rpc_reserved(nth0,3).
iso_rpc_reserved(nth0,4).
iso_rpc_reserved(nth1,3).
iso_rpc_reserved(nth1,4).
iso_rpc_reserved(call_nth,2).
iso_rpc_reserved(time,1).
iso_rpc_reserved(runtime_property,1).
