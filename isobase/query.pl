:- op(200, xfx, @).
% Private worker entry point. Goal and template are parsed together so
% their variables share identity. Optional source is loaded before this query.
iso_query(Text, Template) :-
    atom_concat(Text, '.', FullText),
    read_term_from_atom(FullText, query(Goal, Template), [syntax_error(error)]),
    iso_execute(Goal),
    (acyclic_term(Template) -> true
    ; throw(error(representation_error(cyclic_term),iso_query/2))).

% Fixtures also exercise cleanup of temporary allocations between queries.
iso_numbers(N, X) :- between(1, N, X).
iso_throw_after_one(X) :- (X=first ; throw(later_error)).
iso_alloc(0) :- !.
iso_alloc(N) :- length(L, 100), L=[_|_], M is N-1, iso_alloc(M).

% HTTP JSON answers contain named goal bindings, not the explicit template.
iso_http_json(Text, Rendered) :-
    atom_concat(Text,'.',Full),
    read_term_from_atom(Full,query(Goal,_Template),
                        [syntax_error(error),variable_names(Names)]),
    iso_visible_query_vars(Goal,Names,Vars),iso_visible_names(Names,Vars,Visible),
    iso_execute(Goal),
    (acyclic_term(Visible) -> true
    ; throw(error(representation_error(cyclic_term),iso_http_json/2))),
    iso_render_names(Visible,Visible,Rendered).
iso_visible_names([],_,[]).
iso_visible_names([Name=Var|Ns],Vars,Visible) :-
    (iso_anonymous_name(Name) -> Visible=Rest
    ; iso_var_member(Var,Vars) -> Visible=[Name=Var|Rest]
    ; Visible=Rest),iso_visible_names(Ns,Vars,Rest).
iso_var_member(V,[H|_]) :- V==H,!.
iso_var_member(V,[_|T]) :- iso_var_member(V,T).
iso_render_names([],_,[]).
iso_render_names([N=V|Rest],Names,[N=Text|Rendered]) :-
    iso_write_text(V,[quoted(true),variable_names(Names)],Text),
    iso_render_names(Rest,Names,Rendered).

% One HTTP response is parsed as one Prolog term. Give each answer's free
% variables distinct names, preserving sharing only within that answer.
iso_render_prolog(Term,Serial,Text) :-
    term_variables(Term,Vars),number_codes(Serial,Codes),atom_codes(Id,Codes),
    iso_answer_names(Vars,Id,0,Names),
    % Render in list-element context, so a top-level comma stays one answer.
    iso_write_text([Term],[quoted(true),variable_names(Names)],Wrapped),
    atom_codes(Wrapped,[91|WrappedCodes]),append(Inner,[93],WrappedCodes),atom_codes(Text,Inner).
iso_answer_names([],_,_,[]).
iso_answer_names([V|Vs],Id,N,[Name=V|Names]) :-
    number_codes(N,Codes),atom_codes(Index,Codes),
    atom_concat('_A',Id,P0),atom_concat(P0,'_V',P1),atom_concat(P1,Index,Name),
    N1 is N+1,iso_answer_names(Vs,Id,N1,Names).

% Two passes reproduce the demonstrator's treatment of anonymous helper goals:
% variables inside _Goal=... are hidden unless _Goal is also used as data.
iso_anonymous_name(Name) :- atom_codes(Name,[95,C|_]),
    (C=95;C>=65,C=<90).
iso_visible_query_vars(Goal,Names,Vars) :-
    iso_anon_vars(Names,Anon),
    iso_visibility(refs,Goal,Anon,[],goal,[],Exposed),
    iso_visibility(visible,Goal,Anon,Exposed,goal,[],Vars).
iso_anon_vars([],[]).
iso_anon_vars([N=V|Ns],Anon) :-
    (iso_anonymous_name(N)->Anon=[V|Vs];Anon=Vs),iso_anon_vars(Ns,Vs).
iso_helper_binding(L,R,Anon,L,R) :- var(L),iso_var_member(L,Anon),!.
iso_helper_binding(L,R,Anon,R,L) :- var(R),iso_var_member(R,Anon).
iso_visibility(Mode,T,Anon,_,Context,In,Out) :- var(T),!,
    (Mode==visible->Out=[T|In]
    ;Context==data,iso_var_member(T,Anon)->Out=[T|In];Out=In).
iso_visibility(Mode,L=R,Anon,Exposed,_,In,Out) :-
    iso_helper_binding(L,R,Anon,Helper,Other),!,
    (Mode==refs -> iso_visibility(Mode,Other,Anon,Exposed,data,In,Out)
    ;iso_var_member(Helper,Exposed)->iso_visibility(Mode,Other,Anon,Exposed,data,In,Out)
    ;Out=In).
iso_visibility(Mode,T,Anon,Exposed,_,In,Out) :- compound(T),!,
    iso_visibility_children(T,Children),iso_visibility_list(Children,Mode,Anon,Exposed,In,Out).
iso_visibility(_,_,_,_,_,Vars,Vars).
iso_visibility_children((A,B),[goal-A,goal-B]) :- !.
iso_visibility_children((A;B),[goal-A,goal-B]) :- !.
iso_visibility_children((A->B),[goal-A,goal-B]) :- !.
iso_visibility_children(catch(A,E,B),[goal-A,data-E,goal-B]) :- !.
iso_visibility_children(T,Children) :-
    T=..[F,G|Args],
    ((member(F,[once,ignore,time,(\+)]),Args=[]);F==call),!,
    iso_data_children(Args,Rest),Children=[goal-G|Rest].
iso_visibility_children(T,Children) :- T=..[_|Args],iso_data_children(Args,Children).
iso_data_children([],[]).
iso_data_children([A|As],[data-A|Rest]) :- iso_data_children(As,Rest).
iso_visibility_list([],_,_,_,Vars,Vars).
iso_visibility_list([Context-T|Ts],Mode,Anon,Exposed,In,Out) :-
    iso_visibility(Mode,T,Anon,Exposed,Context,In,Next),
    iso_visibility_list(Ts,Mode,Anon,Exposed,Next,Out).

% A zero-sized page validates the request but never executes its goal.
iso_query_empty(Text,_) :-
    atom_concat(Text,'.',Full),read_term_from_atom(Full,query(Goal,_),[syntax_error(error)]),
    (var(Goal)->throw(error(instantiation_error,iso_query/2));true),
    iso_rewrite(Goal,_),fail.
