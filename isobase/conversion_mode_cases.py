"""Second predicate-audit batch: character and numeric conversion modes."""
def add_cases(case):
    goals=[
        'char_code(C,N)','char_code(a,N)','char_code(C,97)','char_code(a,98)',
        'char_code(42,N)','char_code([],N)','char_code(ab,97)',
        'char_code(a,bad)','char_code(ab,bad)','char_code(C,1.5)',
    ]
    for pred in ['number_codes','number_chars']:
        values=['L','[]','42','[X]','[49,X]','[49|T]','[49|bad]',
                "['1','2']",'[49,50]',"['1',50]","[49,'2']",'[bad]',
                "['1',ab]",'[49,bad]',"[' ','1','2']",'[32,49,50]',
                '[45,48]','[49,46,53]','[49,101,51]']
        for value in values:
            for number in ['N','12']:
                goals.append(f'{pred}({number},{value})')
        for number in ['a','f(x)']:
            goals.append(f'{pred}({number},L)')
        goals.extend([f'{pred}(1.5,L)',f'{pred}(N,[X|bad])',f'{pred}(12,[X|bad])'])
    for goal in goals:
        case('conversion_modes',f'catch(({goal}),error(Form,_),true)',f'result(({goal}),Form)',limit=5)

    for text in ['-2e-2','1E+3','1.5e3','1e','1e+','1e3junk','1e3 ',' 1e3','1e999']:
        for pred in ['number_codes','number_chars']:
            convert='atom_codes' if pred=='number_codes' else 'atom_chars'
            case('conversion_lexical',f"{convert}('{text}',L),catch({pred}(N,L),error(Form,_),true)",'r(N,Form)')
