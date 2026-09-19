% HTTP protocol and source composition stay in Prolog; C owns only transport.
:- foreign(iso_net_start(+string,+integer,term,term)).
:- foreign(iso_net_wait(+integer,+integer,term,term)).
:- foreign(iso_net_peek(+integer,term,term)).
:- foreign(iso_net_unmatched(+integer)).
:- foreign(iso_net_cancel(+integer)).
:- foreign(iso_net_escape(+string,term)).

iso_rpc(Scope,URI,Goal,Options) :-
    iso_rpc_options(Options), iso_remote_goal(Goal),
    term_variables(Goal,Vars),Template=..[v|Vars],
    % rpc freezes its wire goal before option normalization can bind shared
    % variables; promise deliberately captures after normalization instead.
    copy_term(pair(Goal,Template),pair(WireGoal,WireTemplate)),
    iso_rpc_prepare(Scope,URI,WireGoal,WireTemplate,Options,Base,Limit,Once,HTTP),
    iso_rpc_pages(Base,0,Limit,Once,HTTP,Template).
iso_rpc_pages(Base,Offset,Limit,Once,HTTP,Template) :-
    iso_rpc_request(Base,Offset,Limit,HTTP,Ref),
    iso_receive(Ref,-1,Result),
    (Result=success(Slice,More) ->
        (member(Template,Slice)
        ;More==true,Once==false,length(Slice,Count),Count>0,
         Next is Offset+Count,iso_rpc_pages(Base,Next,Limit,Once,HTTP,Template))
    ;Result==failure -> fail
    ;Result=error(Error) -> throw(Error)).

iso_promise(Scope,URI,Goal,Reference,Options) :-
    (var(Reference)->true;throw(error(uninstantiation_error(Reference),promise/4))),
    iso_rpc_options(Options),iso_remote_goal(Goal),
    iso_option(template,Options,Goal,Template),
    iso_option(offset,Options,0,Offset),iso_range(Offset,0,1000000000),
    iso_rpc_prepare(Scope,URI,Goal,Template,Options,Base,Limit,_Once,HTTP),
    iso_rpc_request(Base,Offset,Limit,HTTP,Reference).
% Separate implementation for one-shot receive: no backtracking over IO.
iso_yield_result(Scope,Reference,Message,Options) :-
    iso_integer(Reference),iso_list(Options),iso_yield_options(Options),
    iso_option(timeout,Options,none,Timeout),iso_millis(Timeout,-1,Millis),
    iso_net_wait(Reference,Millis,Text,Status),
    ((Status==timeout;Status==missing) ->
        iso_option(on_timeout,Options,true,OnTimeout),iso_execute_in(Scope,OnTimeout)
    ;iso_transport_result(Status,Text,Message)).
iso_yield_plain(Reference,Message) :-
    iso_integer(Reference),iso_net_peek(Reference,Text,Status),
    Status\==missing,
    catch(iso_transport_result(Status,Text,Result),Error,
          (iso_net_cancel(Reference),throw(Error))),
    (Message=Result -> iso_net_cancel(Reference);iso_net_unmatched(Reference)).
iso_receive(Reference,Millis,Message) :-
    iso_net_wait(Reference,Millis,Text,Status),iso_transport_result(Status,Text,Message).
iso_transport_result(Status,Text,Message) :-
    (Status==ok ->
        catch(read_term_from_atom(Text,Term,[syntax_error(error)]),_,
              throw(error(remote_protocol_error,rpc/3))),
        (nonvar(Term),iso_response(Term)->Message=Term;throw(error(remote_protocol_error,rpc/3)))
    ;throw(error(Status,rpc/3))).
iso_response(failure).
iso_response(error(_)).
iso_response(success(Slice,More)) :- nonvar(Slice),iso_is_list(Slice),(More==true;More==false).

iso_rpc_prepare(Scope,URI,Goal,Template,Options,Base,Limit,Once,HTTP) :-
    iso_option(limit,Options,10000000000,Limit),iso_range(Limit,0,10000000000),
    iso_option(once,Options,false,Once),
    iso_once(Once),
    iso_option(timeout,Options,none,RequestedTimeout),
    (var(RequestedTimeout)->Timeout=none;Timeout=RequestedTimeout),
    % Reject remote deadlines before composing or fetching source.
    (Timeout==none->true;iso_millis(Timeout,0,_)),
    iso_source_options(Scope,Options,Source),
    iso_option(http_timeout,Options,30,HT),iso_http_millis(HT,HTTP),
    % Assign one set of variable names across Goal and Template.
    term_variables(pair(Goal,Template),Vars),iso_wire_names(Vars,0,Names),
    iso_write_text(Goal,[quoted(true),ignore_ops(false),variable_names(Names)],G),
    iso_write_text(Template,[quoted(true),ignore_ops(false),variable_names(Names)],T),
    iso_uri(URI,U),atom_concat(U,'/call?format=prolog',B0),
    iso_param(B0,goal,G,B1),iso_param(B1,template,T,B2),
    iso_param(B2,src_text,Source,B3),iso_param(B3,once,Once,B4),
    (Timeout==none -> Base=B4
    ;iso_param(B4,timeout,Timeout,Base)).
iso_rpc_request(Base,Offset,Limit,HTTP,Reference) :-
    iso_param(Base,offset,Offset,B),iso_param(B,limit,Limit,URL),
    iso_net_start(URL,HTTP,Reference,Status),
    (Status==ok->true;throw(error(Status,promise/4))).
iso_wire_names([],_,[]).
iso_wire_names([V|Vs],I,[Name=V|Ns]) :- iso_number_atom(I,A),atom_concat('V',A,Name),
    J is I+1,iso_wire_names(Vs,J,Ns).
iso_param(Base,Key,Value,Out) :-
    (atom(Value)->Atom=Value;iso_number_atom(Value,Atom)),
    (iso_net_escape(Atom,Encoded)->true;throw(error(request_too_large,rpc/3))),
    atom_concat(Base,'&',A),atom_concat(A,Key,B),atom_concat(B,'=',C),atom_concat(C,Encoded,Out).
iso_uri(URI0,URI) :-
    iso_source_uri(URI0,A),
    (sub_atom(A,_,1,0,'/')->atom_length(A,N),M is N-1,sub_atom(A,0,M,1,URI);URI=A).
% A source URL identifies an exact resource, not a node base URL.
iso_source_uri(Host:Port,URI) :- nonvar(Host),atom(Host),integer(Port),!,
    iso_number_atom(Port,P),atom_concat('http://',Host,A),atom_concat(A,':',B),atom_concat(B,P,URI).
iso_source_uri(URI0,A) :-
    iso_text(URI0,A),
    ((sub_atom(A,0,7,_,'http://');sub_atom(A,0,8,_,'https://'))->true
    ;throw(error(domain_error(http_uri,A),rpc/3))).

iso_source_options(Scope,Options,Source) :-
    iso_option(http_timeout,Options,30,HT),
    % Local source errors precede transport validation. A download validates
    % its deadline before I/O; preparation validates it again for the RPC.
    iso_source_parts(Scope,Options,HT,Parts),iso_join_sources(Parts,Source).
iso_source_parts(_,[],_,[]).
iso_source_parts(Scope,[O|Os],HT,Parts) :-
    (O=src_text(Text)->iso_text(Text,S),Parts=[S|Rest]
    ;O=src_list(Terms)->iso_list(Terms),iso_terms_source(Terms,S),Parts=[S|Rest]
    ;O=src_predicates(PIs)->iso_list(PIs),iso_export(Scope,PIs,Terms),iso_terms_source(Terms,S),Parts=[S|Rest]
    ;O=src_uri(URI)->iso_source_uri(URI,U),iso_http_millis(HT,HTTP),iso_net_start(U,HTTP,R,Status),
        (Status==ok->true;throw(error(Status,rpc/3))),
        iso_net_wait(R,-1,S,Result),(Result==ok->true;throw(error(Result,rpc/3))),Parts=[S|Rest]
    ;Parts=Rest),iso_source_parts(Scope,Os,HT,Rest).
iso_export(_,[],[]).
iso_export(Scope,[PI|PIs],Terms) :-
    (nonvar(PI),PI=F/N,atom(F),integer(N),N>=0,N=<255->true
    ;throw(error(type_error(predicate_indicator,PI),rpc/3))),
    (Scope==local,iso_owned(F,N)->true
    ;throw(error(permission_error(access,procedure,PI),rpc/3))),
    functor(H,F,N),findall((H:-B),iso_original_clause(H,B),Clauses),
    (Clauses=[]->Here=[(:-dynamic(F/N))];Here=Clauses),
    iso_export(Scope,PIs,Rest),append(Here,Rest,Terms).
iso_terms_source([], '').
iso_terms_source([T|Ts],Source) :-
    iso_write_text(T,[quoted(true),ignore_ops(false)],A),atom_concat(A,'.\n',B),
    iso_terms_source(Ts,Rest),atom_concat(B,Rest,Source).
iso_join_sources([], '').
iso_join_sources([S|Ss],Text) :- iso_join_sources(Ss,Rest),atom_concat(S,'\n',A),atom_concat(A,Rest,Text).
iso_text(T,A) :- (atom(T)->A=T;iso_is_list(T)->
    (T=[H|_],integer(H)->iso_text_codes(A,T);iso_text_chars(A,T))
    ;throw(error(type_error(text,T),rpc/3))).
iso_option(Name,Options,Default,Value) :-
    (member(O,Options),functor(O,Name,1)->arg(1,O,Value);Value=Default).
iso_remote_goal(G) :-
    (var(G)->throw(error(instantiation_error,rpc/3));callable(G)->true
    ;throw(error(type_error(callable,G),rpc/3))),
    (acyclic_term(G)->true;throw(error(representation_error(cyclic_term),rpc/3))).
iso_integer(I) :- (integer(I)->true;var(I)->throw(error(instantiation_error,rpc/3));throw(error(type_error(integer,I),rpc/3))).
iso_range(I,Min,Max) :- iso_integer(I),(I>=Min,I=<Max->true;throw(error(domain_error(request_range,I),rpc/3))).
iso_once(true) :- !.
iso_once(false) :- !.
iso_once(Value) :- throw(error(domain_error(boolean,Value),rpc/3)).
iso_http_millis(T,HTTP) :-
    (T==none->throw(error(type_error(number,T),rpc/3));true),
    iso_millis(T,30000,Millis),HTTP is max(1,Millis).
iso_millis(T,Default,Default) :- T==none,!.
iso_millis(T,_,M) :-
    (number(T)->true;var(T)->throw(error(instantiation_error,rpc/3));throw(error(type_error(number,T),rpc/3))),
    (T>=0,T=<300->(integer(T)->M is T*1000;M is ceiling(T*1000));throw(error(domain_error(timeout,T),rpc/3))).
iso_is_list(L) :- nonvar(L),(L=[];L=[_|T],iso_is_list(T)).
iso_list(L) :-
    (acyclic_term(L)->true;throw(error(representation_error(cyclic_term),rpc/3))),
    (iso_is_list(L)->true;throw(error(type_error(list,L),rpc/3))).
iso_rpc_options(Os) :- iso_list(Os),iso_check_options(Os).
iso_check_options([]).
iso_check_options([O|Os]) :-
    (nonvar(O),functor(O,F,1),member(F,[limit,offset,template,once,timeout,http_timeout,src_text,src_list,src_predicates,src_uri])->true
    ;throw(error(domain_error(rpc_option,O),rpc/3))),iso_check_options(Os).
iso_yield_options([]).
iso_yield_options([O|Os]) :-
    (nonvar(O),(O=timeout(_);O=on_timeout(_))->true
    ;throw(error(domain_error(yield_option,O),yield/3))),iso_yield_options(Os).

iso_number_atom(N,A) :- number_codes(N,C),atom_codes(A,C).
