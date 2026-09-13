"""Selected DCG grammar bodies, list modes and source expansion."""
def add_cases(case):
    for body in ['[]','[a]','[a,b]','{}','{true}','{fail}','{throw(ball)}',
                 '([a];[b])','([a]->[b];[c])','(\\+ [b],[a])',
                 '(!,[a])','B','42','[a|T]','[a|bad]']:
        for inp,out in [('L','[]'),('[a,b]','R'),('bad','[]')]:
            goal=f'phrase(({body}),{inp},{out})'
            case('dcg_argument_modes',f'catch(({goal}),Ball,(Ball=error(Form,_)->E=error(Form);E=Ball))',f'r(({goal}),E)',limit=5)
    examples=[
        ('word --> [].','phrase(word,L)','L'),
        ('word --> {}.','phrase(word,L)','L'),
        ('word --> {X=a},[X].','phrase(word,L)','L'),
        ('word --> G,{G=[a]},G.','phrase(word,[a])','ok'),
        ('word --> {G=[a]},G.','phrase(word,L)','L'),
        ('word(G) --> G.','phrase(word([a,b]),L)','L'),
        ('word --> call(token). token --> [a].','phrase(word,L)','L'),
        ('word --> [a],!,[b]. word --> [a],[c].','phrase(word,[a,c])','ok'),
        ('word --> ([a]->[b];[c]).','phrase(word,L)','L'),
        ('word --> \\+ [b],[a].','phrase(word,[a])','ok'),
        ('word, [b] --> [a].','phrase(word,[a],R)','R'),
        ('word --> [a|T].','phrase(word,[a])','ok'),
        ('word --> [a|bad].','phrase(word,[a])','ok'),
        ('word --> 42.','phrase(word,[])','ok'),
        ('word --> [a].','phrase(word,[a|bad],R)','R'),
        ('word --> [a].','phrase(word,L,[z])','L'),
    ]
    for source,goal,template in examples:
        if source in ['word --> [a|T].','word --> [a|bad].','word --> 42.']:
            case('rejection',goal,template,source)
        else:
            case('dcg_source_modes',f'catch(({goal}),error(Form,_),true)',f'r({template},Form)',source)

    for goal in ['phrase({write(a)},[])','G={write(a)},phrase(G,[])',
                 'phrase(([],{write(a)}),[])','phrase(call(bad),[])']:
        case('rejection',goal,source='bad(_,_) :- write(a).' if 'call(bad)' in goal else '')
    for source in ['word --> ({},[a]).','word --> ([];{}),[a].',
                   'word --> {G=([a],[b])},G.',
                   'word --> call(token,x). token(x) --> [a].']:
        case('dcg_source_modes','phrase(word,L)','L',source)
    case('dcg_source_modes','phrase(word,L)','L','word --> [X],{X=a}.')
    case('dcg_source_modes','phrase(word,[a|bad],R),R==bad','ok','word --> [a].')
    for source in ['word --> [a.', 'word --> .', '42 --> [a].']:
        case('rejection','true','ok',source)
    case('dcg_source_modes','phrase(word,L)','L','word --> "ab".')
