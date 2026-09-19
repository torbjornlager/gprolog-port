"""URI and validation-order samples; source HTTP fixtures live in rpc_source_tests."""
def add_cases(case):
    uri="'__RPC_TARGET__'"
    for opts in [
        '[once(bad),timeout(bad)]', '[timeout(bad),src_text(42)]',
        '[timeout(bad),src_list(bad)]', '[timeout(bad),http_timeout(bad)]',
        '[once(bad),src_text(42)]', '[src_text(42),src_list(bad)]',
        '[src_list(bad),src_text(42)]', '[src_text(42),http_timeout(bad)]',
        '[http_timeout(bad),src_list(bad)]',
        '[timeout(none),timeout(bad)]', '[http_timeout(none)]',
        '[timeout(0.5)]', '[http_timeout(0.5)]', '[timeout(300)]',
        '[http_timeout(300)]', '[limit(1),offset(bad)]',
        '[template(ignored),offset(bad)]',
    ]:
        case('rpc_boundary_validation',f'catch(rpc({uri},true,{opts}),error(E,_),true)','E')
    for opts in ['[timeout(bad),src_text(42)]','[once(bad),timeout(bad)]',
                 '[src_text(42),http_timeout(bad)]','[timeout(T)]',
                 '[http_timeout(T)]','[timeout(0.5)]','[http_timeout(0.5)]']:
        case('rpc_boundary_promise',
             f'catch((promise({uri},true,R,{opts}),yield(R,M)),error(E,_),true)','r(M,E)')
    # GNU intentionally allows only the listed public options and caps timeouts.
    for option in ['unknown(x)','request_header(x=y)','redirect(false)',
                   'cert_verify_hook(accept)','method(post)']:
        case('rpc_boundary_options',
             f'catch(rpc({uri},true,[{option}]),error(E,_),true)','E',
             expected_gnu=f'success([domain_error(rpc_option,{option})],false).')
    for option in ['timeout(301)','http_timeout(301)']:
        case('rpc_boundary_options',f'catch(rpc({uri},true,[{option}]),error(E,_),true)','E',
             expected_gnu='success([domain_error(timeout,301)],false).')
    for suffix in ['', '/', '/nested', '/nested/', '?old=value', '#fragment']:
        # Classify endpoint failure separately from its host-specific HTTP diagnostic.
        goal=f"catch((rpc('__RPC_TARGET__{suffix}',true),S=ok),_,S=error)"
        opts={} if suffix in ['', '/'] else {'expected_gnu':'success([error],false).'}
        case('rpc_boundary_uri',goal,'S',**opts)
    for suffix in ['/source/', '/source%20name', '/source?name=a%2Fb']:
        case('rpc_boundary_source',
             f"rpc({uri},p(X),[src_uri('__SOURCE_TARGET__{suffix}')])",'X')
    for options in [
        "src_uri('__SOURCE_TARGET__/a'),src_uri('__SOURCE_TARGET__/b')",
        "src_uri('__SOURCE_TARGET__/b'),src_uri('__SOURCE_TARGET__/a')",
        "src_text('p(local).'),src_uri('__SOURCE_TARGET__/a')",
        "src_uri('__SOURCE_TARGET__/a'),src_list([p(local)])",
    ]:
        case('rpc_boundary_source',f'rpc({uri},p(X),[{options}])','X')
    for alias in ['localhost','local','self']:
        case('rpc_boundary_alias',f'catch(rpc({alias},true),error(E,_),true)','E',
             expected_gnu=f'success([domain_error(http_uri,{alias})],false).')
    for conversion in ['atom_codes','atom_chars']:
        case('rpc_boundary_uri',
             f"{conversion}('__RPC_TARGET__',U),rpc(U,true)",
             expected_gnu='success([ok],false).')
    for target in ["'http://'", "'http://127.0.0.1:bad'", "'http://127.0.0.1:65536'"]:
        # SWI fails silently for the alphabetic port; GNU reports a transport error.
        opts={'expected_gnu':'success([error],false).'} if ':bad' in target else {}
        case('rpc_boundary_uri',f'catch((rpc({target},true),S=ok),_,S=error)','S',**opts)
    for opts in ['[http_timeout(none)]','[timeout(bad),http_timeout(none)]',
                 '[src_list(bad),src_text(42)]','[src_text(42),src_list(bad)]',
                 '[once(bad),src_list(bad)]','[http_timeout(T),src_text(42)]']:
        case('rpc_boundary_promise',
             f'catch((promise({uri},true,R,{opts}),yield(R,M)),error(E,_),true)','r(M,E)')
