"""Text and arithmetic boundary probes; differences must be classified."""
def add_cases(case):
    for atom in ["'å'","'東京'","'😀'","'é'"]:
        for goal,template in [(f'atom_length({atom},N)','N'),(f'atom_codes({atom},C)','C'),(f'atom_chars({atom},C)','C'),(f'atom_concat(A,B,{atom})','A-B'),(f'sub_atom({atom},B,1,A,S)','r(B,A,S)')]:
            case('unicode',goal,template)
    for goal,template in [("char_code('å',C)",'C'),("char_code('😀',C)",'C'),('char_code(C,128512)','C'),('atom_codes(A,[229,26481,128512])','A'),("atom_chars(A,['å','東','😀'])",'A')]:
        case('unicode',f'catch(({goal}),error(E,_),true)',f'r({template},E)')
    for expression in ['1152921504606846975','-1152921504606846976','1.0e308*10','1.0/0.0','sqrt(-1)','log(0)','2^(-1)','-7//3','-7 mod 3','-7 rem 3']:
        case('numeric_boundary',f'catch((X is {expression}),error(E,_),true)','r(X,E)')
    for expression in ['1152921504606846975+1','-1152921504606846976-1','2^60','2**60','1<<60']:
        case('host_boundary',f'catch((X is {expression}),error(E,_),true)','r(X,E)',
             expected_gnu='success([r(_,evaluation_error(int_overflow))],false).')
    case('host_boundary','X="abc"','X',expected_gnu='success([[97,98,99]],false).')
    case('host_boundary','catch(char_code(C,0),error(E,_),true)','E',
         expected_gnu='success([representation_error(character_code)],false).')
    for code in [127,128,2047,2048,55295,57344,65535,65536,1114111]:
        case('unicode',f'char_code(C,{code}),char_code(C,N)','N')
    for goal in ["char_code(a,1.5)","char_code(C,-1)","char_code(ab,C)",
                 "sub_atom('å',-1,L,A,S)","sub_atom('å',a,L,A,S)"]:
        case('text_errors',f'catch(({goal}),error(E,_),true)','E')
    case('unicode',"atom_chars('a\\\\x9d\\\\b',C),atom_chars(A,C),A=='a\\\\x9d\\\\b'",'ok')

