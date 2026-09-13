"""First predicate-audit batch: atomic text and list argument modes."""
def add_cases(case):
    goals=[
        'atom_codes(A,C)','atom_codes(a,C)','atom_codes(a,[97])','atom_codes(a,[98])',
        'atom_codes(a,42)','atom_codes(a,[bad])','atom_codes(a,[97|bad])',
        'atom_codes(a,[X])','atom_codes(a,[97|Tail])','atom_codes(A,[X])',
        'atom_codes(A,[97|Tail])','atom_codes(A,[97|bad])','atom_codes(42,C)',
        "atom_chars(A,C)","atom_chars(a,[a])","atom_chars(a,[b])",
        "atom_chars(a,42)","atom_chars(a,[42])","atom_chars(a,[ab])",
        "atom_chars(a,[a|bad])","atom_chars(a,[X])","atom_chars(a,[a|Tail])",
        "atom_chars(A,[X])","atom_chars(A,[a|Tail])","atom_chars(42,C)",
        'atom_length(A,N)','atom_length(a,0)','atom_length(a,-1)','atom_length(a,x)',
        'atom_length(A,1)','atom_concat(A,B,C)','atom_concat(a,b,ab)',
        'atom_concat(a,b,ac)','atom_concat(42,b,C)','atom_concat(42,B,\'42b\')',
        'sub_atom(abc,B,L,A,S)','sub_atom(abc,B,0,A,S)','sub_atom(abc,0,1,2,b)',
        'sub_atom(abc,0,1,2,ab)','sub_atom(abc,0,2,1,ab)','sub_atom(abc,B,L,A,42)',
        'length([a,b],2)','length([a,b],1)','length([a|T],2)',
        'length([a|T],0)','length([a|bad],0)','length([a|bad],-1)',
        'length([a],x)','length(L,1.5)','length(L,L)',
        'member(X,[a|bad])','append(A,B,[a,b])','select(X,[a,b],R)',
        'nth0(0,[a|bad],X)','nth0(1,[a|bad],X)',
    ]
    for goal in goals:
        # Preserve original variables while also recording catchable formal errors.
        case('predicate_modes',f'catch(({goal}),error(Form,_),true)',f'result(({goal}),Form)',limit=12)
    # Cyclic elements do not make a finite list spine cyclic.
    case('list_cycles','X=f(X),length([X],N)','N')
    case('list_cycles','X=f(X),length([X,a],N)','N')
    case('list_cycles','L=[a|L],catch(length(L,N),error(_,_),Status=caught)','Status')
