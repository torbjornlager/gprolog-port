"""Source composition and RPC options against a shared disposable GNU target."""
def add_cases(case):
    uri="'__RPC_TARGET__'"
    for options in ['[]','[limit(1)]','[limit(2)]','[limit(0)]',
                    '[limit(1),limit(2)]','[limit(2),limit(1)]',
                    '[once(true),limit(1)]','[once(false),limit(1)]',
                    '[once(false),once(true),limit(1)]',
                    '[offset(2),limit(1)]','[template(ignored),limit(1)]',
                    '[timeout(none)]','[timeout(T)]','[http_timeout(1)]',
                    '[once(bad)]','[once(X)]','[timeout(-1)]','[timeout(bad)]',
                    '[http_timeout(-1)]','[http_timeout(bad)]']:
        goal=f'rpc({uri},member(X,[a,b,c]),{options})'
        boundary={}
        if options in ['[timeout(-1)]','[http_timeout(-1)]']:
            boundary['expected_gnu']='success([r(_,domain_error(timeout,-1))],false).'
        case('rpc_option_modes',f'catch(({goal}),error(Form,_),true)','r(X,Form)',**boundary)
    sources=["[src_text('p(a).')]","[src_list([p(a),p(b)])]",
             "[src_text('p(a).'),src_text('p(b).')]",
             "[src_list([p(a)]),src_text('p(b).')]",
             "[src_text('p(a).'),src_list([p(b)])]",
             "[src_list([]),src_text('p(a).')]",
             "[src_predicates([p/1])]", "[src_predicates([p/1,p/1])]",
             "[src_predicates([p/1]),src_text('p(c).')]",
             "[src_text('p(c).'),src_predicates([p/1])]",
             "[src_text([112,40,97,41,46])]",
             "[src_text([p,'(',a,')','.'])]"]
    for options in sources:
        goal=f'rpc({uri},p(X),{options})'
        case('rpc_source_options',f'catch(({goal}),error(Form,_),true)','r(X,Form)','p(a). p(b).')
    for opts in ['[limit(1)]','[offset(1),limit(1)]','[offset(2),limit(1)]',
                 '[template(X),offset(1),limit(1)]',
                 '[template((X,X)),limit(1)]','[once(true),limit(2)]']:
        goal=f'promise({uri},member(X,[a,b,c]),R,{opts}),yield(R,M)'
        case('promise_option_modes',f'catch(({goal}),error(Form,_),true)','r(M,Form)')
    for target in ["'__RPC_TARGET__/'", "'127.0.0.1':__RPC_PORT__"]:
        case('rpc_uri_modes',f'rpc({target},member(X,[a,b]))','X')
    for opts in ['[limit(1),limit(bad)]','[once(false),once(bad)]',
                 '[timeout(none),timeout(bad)]','[http_timeout(1),http_timeout(bad)]',
                 '[once(O)]','[timeout(T)]','[http_timeout(T)]',
                 '[src_list(bad)]','[src_predicates(bad)]','[src_text(42)]',
                 '[src_list([])]','[src_predicates([])]']:
        goal=f'rpc({uri},true,{opts})'
        case('rpc_validation_modes',f'catch(({goal}),error(Form,_),true)','r(O,T,Form)')
    for source,options in [
        ('p(L):-phrase([a],L).','[src_predicates([p/1])]'),
        ('p(a). p(b).',"[src_list([p(z)]),src_text('p(c).'),src_predicates([p/1])]"),
        ('p(a). p(b).',"[src_predicates([p/1]),src_list([p(c),p(d)])]"),
    ]:
        case('rpc_source_options',f'rpc({uri},p(X),{options})','X',source)
    case('rpc_source_isolation',f'rpc({uri},p(a),[src_list([p(a)])]),catch(rpc({uri},p(a)),error(permission_error(execute,isobase,p/1),_),Status=isolated)','Status')
    for options in ['[offset(1),offset(2),limit(1)]',
                    '[offset(1),limit(1),template(X),template(ignored)]',
                    "[src_list([p(a),p(b)]),template(X),limit(1)]"]:
        remote='p(X)' if 'src_list' in options else 'member(X,[a,b,c])'
        case('promise_option_modes',f'promise({uri},{remote},R,{options}),yield(R,M)','M')

    case('rpc_option_aliasing',f'catch(rpc({uri},throw(O),[once(O)]),Ball,(Ball=error(Form,_)->E=Form;E=Ball))','r(O,E)')
    case('rpc_option_aliasing',f'promise({uri},throw(O),R,[once(O)]),yield(R,M)','r(O,M)')
