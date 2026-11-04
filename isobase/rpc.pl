% HTTP protocol and source composition stay in Prolog; C owns only transport.
:- foreign(iso_net_start(+string,+integer,+string,+string,+string,term,term)).
:- foreign(iso_net_wait(+integer,+integer,term,term)).
:- foreign(iso_net_peek(+integer,term,term)).
:- foreign(iso_net_unmatched(+integer)).
:- foreign(iso_net_cancel(+integer)).
:- foreign(iso_net_escape(+string,term)).
:- foreign(iso_net_node_uri(+string)).
:- foreign(iso_net_nonce(term)).

iso_rpc(Scope,URI,Goal,Options) :-
    iso_rpc_options(Scope,rpc,Options), iso_remote_goal(Goal),
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
    iso_rpc_options(Scope,promise,Options),iso_remote_goal(Goal),
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
    ;iso_promise_transport_result(Status,Text,Message)).
iso_yield_plain(Reference,Message) :-
    iso_integer(Reference),iso_net_peek(Reference,Text,Status),
    Status\==missing,
    catch(iso_promise_transport_result(Status,Text,Result),Error,
          (iso_net_cancel(Reference),throw(Error))),
    (Message=Result -> iso_net_cancel(Reference);iso_net_unmatched(Reference)).
iso_receive(Reference,Millis,Message) :-
    iso_net_wait(Reference,Millis,Text,Status),iso_transport_result(Status,Text,Message).
iso_transport_result(Status,Text,Message) :-
    (Status==http_timeout -> throw(error(rpc_error(http_timeout),rpc/3))
    ;Status==ok ->
        catch(read_term_from_atom(Text,Term,[syntax_error(error)]),_,
              throw(error(remote_protocol_error,rpc/3))),
        (nonvar(Term),iso_response(Term)->Message=Term;throw(error(remote_protocol_error,rpc/3)))
    ;throw(error(Status,rpc/3))).
iso_promise_transport_result(http_timeout,_,error(error(rpc_error(http_timeout),rpc/3))) :- !.
iso_promise_transport_result(Status,Text,Message) :- iso_transport_result(Status,Text,Message).
iso_response(failure).
iso_response(error(_)).
iso_response(success(Slice,More)) :- nonvar(Slice),iso_is_list(Slice),(More==true;More==false).

iso_rpc_prepare(Scope,URI,Goal,Template,Options,Base,Limit,Once,HTTP) :-
    iso_option(limit,Options,10000000000,Limit),iso_range(Limit,0,10000000000),
    iso_option(once,Options,false,Once),
    iso_once(Once),
    iso_option(timeout,Options,none,RequestedTimeout),
    (RequestedTimeout==none->Timeout=none;Timeout is max(0,RequestedTimeout)),
    % Reject remote deadlines before composing or fetching source.
    (Timeout==none->true;iso_timeout_number(Timeout)),
    % Validate the node address before any src_uri download or request slot.
    iso_uri(URI,U),
    iso_source_options(Scope,Options,Source),
    iso_option(http_timeout,Options,30,HT),iso_http_millis(HT,HTTP),
    % Assign one set of variable names across Goal and Template.
    term_variables(pair(Goal,Template),Vars),iso_wire_names(Vars,0,Names),
    iso_rpc_wire_text(Goal,Names,G),iso_rpc_wire_text(Template,Names,T),
    atom_concat(U,'/call?format=prolog',B0),
    iso_param(B0,goal,G,B1),iso_param(B1,template,T,B2),
    iso_param(B2,src_text,Source,B3),iso_param(B3,once,Once,B4),
    (Timeout==none -> URL=B4
    ;iso_param(B4,timeout,Timeout,URL)),
    rpc_http_fields(Options,Fields),rpc_http_wire_lines(Fields,Headers),
    (iso_net_nonce(Owner)->Base=owned(URL,Owner,Headers);throw(error(entropy_unavailable,rpc/3))).
% Frame each term independently before URL encoding: peers may parse the
% fields together to preserve shared variables. Keep the same Names for both.
iso_rpc_wire_text(Term,Names,Text) :-
    iso_write_text(Term,[quoted(true),ignore_ops(false),variable_names(Names)],Raw),
    atom_concat('(',Raw,Prefix),atom_concat(Prefix,')',Text).

iso_rpc_request(owned(Base,Owner,Headers),Offset,Limit,HTTP,Reference) :-
    iso_param(Base,offset,Offset,B),iso_param(B,limit,Limit,URL),
    iso_net_start(URL,HTTP,rpc,Owner,Headers,Reference,Status),
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
    (iso_net_node_uri(A)->true;throw(error(domain_error(http_uri,A),rpc/3))),
    (sub_atom(A,_,1,0,'/')->atom_length(A,N),M is N-1,sub_atom(A,0,M,1,URI);URI=A).
% A source URL identifies an exact resource, not a node base URL.
iso_source_uri(URI0,A) :-
    (var(URI0)->throw(error(instantiation_error,rpc/3));true),
    (atom(URI0)->A=URI0;throw(error(type_error(atom,URI0),rpc/3))),
    ((sub_atom(A,0,7,_,'http://');sub_atom(A,0,8,_,'https://'))->true
    ;throw(error(domain_error(http_uri,A),rpc/3))).

iso_source_options(Scope,Options,Source) :-
    % Source downloads use their own default, independently of request options.
    HT=30,
    iso_source_parts(Scope,Options,HT,Parts),iso_join_sources(Parts,Source).
iso_source_parts(_,[],_,[]).
iso_source_parts(Scope,[O|Os],HT,Parts) :-
    (O=src_text(Text)->iso_text(Text,S),Parts=[S|Rest]
    ;O=src_list(Terms)->iso_list(Terms),iso_terms_source(Terms,S),Parts=[S|Rest]
    ;O=src_predicates(PIs)->iso_list(PIs),iso_export(Scope,PIs,Terms),iso_terms_source(Terms,S),Parts=[S|Rest]
    ;O=src_uri(URI)->iso_source_uri(URI,U),iso_http_millis(HT,HTTP),iso_net_start(U,HTTP,source,'','',R,Status),
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
iso_once(Value) :-
    (var(Value)->throw(error(instantiation_error,rpc/3))
    ;\+atom(Value)->throw(error(type_error(atom,Value),rpc/3))
    ;Value==true->true
    ;Value==false->true
    ;throw(error(domain_error(boolean,Value),rpc/3))).
iso_timeout_number(T) :-
    (number(T)->true;var(T)->throw(error(instantiation_error,rpc/3));throw(error(type_error(number,T),rpc/3))).
iso_http_millis(T,HTTP) :-
    iso_timeout_number(T),Seconds is max(0,T),
    (integer(Seconds)->HTTP is Seconds*1000;HTTP is ceiling(Seconds*1000)).
iso_millis(T,Default,Default) :- T==none,!.
iso_millis(T,_,M) :-
    (number(T)->true;var(T)->throw(error(instantiation_error,rpc/3));throw(error(type_error(number,T),rpc/3))),
    (T>=0,T=<300->(integer(T)->M is T*1000;M is ceiling(T*1000));throw(error(domain_error(timeout,T),rpc/3))).
iso_is_list(L) :- nonvar(L),(L=[];L=[_|T],iso_is_list(T)).
iso_list(L) :-
    (acyclic_term(L)->true;throw(error(representation_error(cyclic_term),rpc/3))),
    (iso_is_list(L)->true;throw(error(type_error(list,L),rpc/3))).
% Validate every occurrence before source fetching or network dispatch.
iso_rpc_options(Scope,Kind,Os) :-
    (acyclic_term(Os)->true;throw(error(representation_error(cyclic_term),rpc/3))),
    iso_rpc_list_shape(Os,Os),iso_check_options(Scope,Kind,Os).
iso_rpc_list_shape(List,Original) :-
    (var(List)->throw(error(instantiation_error,rpc/3))
    ;List==[]->true
    ;List=[_|Rest]->iso_rpc_list_shape(Rest,Original)
    ;throw(error(type_error(list,Original),rpc/3))).
iso_check_options(_,_,[]).
iso_check_options(Scope,Kind,[O|Os]) :-
    (var(O)->throw(error(instantiation_error,rpc/3));true),
    (functor(O,F,1),member(F,[limit,offset,template,once,timeout,http_timeout,src_text,src_list,src_predicates,src_uri,request_header,authorization,user_agent]),
     (Kind==promise;F\==offset,F\==template)->true
    ;atom_concat(Kind,'_option',Domain),throw(error(domain_error(Domain,O),rpc/3))),
    arg(1,O,V),iso_rpc_option_value(Scope,F,V),iso_check_options(Scope,Kind,Os).
iso_rpc_option_value(_,request_header,V) :- rpc_http_validate(request_header(V)).
iso_rpc_option_value(_,authorization,V) :- rpc_http_validate(authorization(V)).
iso_rpc_option_value(_,user_agent,V) :- rpc_http_validate(user_agent(V)).
iso_rpc_option_value(_,limit,V) :-
    iso_integer(V),(V>0->iso_range(V,1,10000000000);throw(error(type_error(positive_integer,V),rpc/3))).
iso_rpc_option_value(_,offset,V) :- iso_range(V,0,1000000000).
iso_rpc_option_value(_,template,_).
iso_rpc_option_value(_,once,V) :- iso_once(V).
iso_rpc_option_value(_,timeout,V) :- iso_timeout_number(V).
iso_rpc_option_value(_,http_timeout,V) :- iso_http_millis(V,_).
iso_rpc_option_value(_,src_uri,V) :- iso_source_uri(V,_).
iso_rpc_option_value(_,src_text,V) :- iso_text(V,_).
iso_rpc_option_value(_,src_list,V) :- iso_list(V).
iso_rpc_option_value(Scope,src_predicates,V) :- iso_list(V),iso_export(Scope,V,_).
iso_yield_options([]).
iso_yield_options([O|Os]) :-
    (nonvar(O),(O=timeout(_);O=on_timeout(_))->true
    ;throw(error(domain_error(yield_option,O),yield/3))),
    (O=timeout(T)->iso_millis(T,-1,_);O=on_timeout(Goal),iso_remote_goal(Goal)),
    iso_yield_options(Os).

iso_number_atom(N,A) :- number_codes(N,C),atom_codes(A,C).

:- include(rpc_http_fields).
rpc_http_string_chars(_,_) :- fail.

rpc_http_host_utf8([],[]).
rpc_http_host_utf8([C|Cs],[B|Bs]) :- char_code(C,B),rpc_http_host_utf8(Cs,Bs).

rpc_http_native_value(Value,Value).

% GNU's atoms expose UTF-8 bytes; normalize explicit scalar-character lists.
rpc_http_one_char(C,Chars) :- atom(C),C\==[],atom_codes(C,Bytes),
    rpc_http_utf8_scalar(Bytes),atom_chars(C,Chars).
rpc_http_utf8_scalar([A]) :- A>=0,A=<127.
rpc_http_utf8_scalar([A,B]) :- A>=194,A=<223,rpc_http_continuation(B).
rpc_http_utf8_scalar([A,B,C]) :- A>=224,A=<239,rpc_http_continuation(B),rpc_http_continuation(C),
    (A=:=224->B>=160;A=:=237->B=<159;true).
rpc_http_utf8_scalar([A,B,C,D]) :- A>=240,A=<244,
    rpc_http_continuation(B),rpc_http_continuation(C),rpc_http_continuation(D),
    (A=:=240->B>=144;A=:=244->B=<143;true).
rpc_http_continuation(B) :- B>=128,B=<191.
