"""Numeric lexical, formatting and round-trip samples."""
def add_cases(case):
    texts=['0','-0','+12','0012',' 12','12 ','12\n','\t12','1_000','1__000','1_','_1',
           '1 000','1_ 000','0xff','0XFF','0b101','0o77',"16'ff","2'101","0'a",
           '0x','0b2','0o8','.5','1.','1.0','-0.0','+1.25','1.2_5','1.0e1_0',
           '1e-999','1.0e-320','1.7976931348623157e308','1.8e308',
           '1152921504606846975','-1152921504606846976',
           '1152921504606846976','-1152921504606846977','1r2','1.0Inf','1.5NaN',
           'nan','inf','12/*x*/','12%comment','１２','١٢']
    texts += ['1  000','1\t000','1\n000','1_\t000','1_ 000 ',
              '0xF_F',"16'f_f",'+ 1','+-1','-+1',"37'z","1'0","02'10","16'FF",
              '-0xff',"-16'ff",'0x_FF','0xFF_','1_000.0','1 000.0',
              '1_000e2','1_000.5e-2','0b1_0','0o7 7','1__0',
              "36'z","2'2",'0x1000000000000000','-0x1000000000000000']
    for text in texts:
        codes='['+','.join(str(ord(c)) for c in text)+']'
        for pred in ['number_codes','number_chars']:
            setup=f'L={codes}' if pred=='number_codes' else f'atom_codes(A,{codes}),atom_chars(A,L)'
            options={}
            if text in ['0x1000000000000000','1152921504606846976','-1152921504606846977','1r2','1.0Inf','1.5NaN','１２','١٢']:
                options['expected_gnu']='success([r(_,syntax_error(illegal_number))],false).'
            case('numeric_lexical',f'{setup},catch({pred}(N,L),error(E,_),true)','r(N,E)',**options)
    for value in ['0','-12','1152921504606846975','-1152921504606846976','0.0','-0.0',
                  '1.0','0.1','1.2345678901234567','1.0e-7','1.0e20','1.0e100','1.0e-320','0.0001','0.00001','10000.0','100000.0','1.234567890123456','2.2250738585072014e-308','4.9406564584124654e-324']:
        for pred in ['number_codes','number_chars']:
            case('numeric_format',f'{pred}({value},L)','L')
            case('numeric_roundtrip',f'{pred}({value},L),{pred}(N,L),N==({value})','ok')
    # Deterministic binary64 samples, with decimal literals retaining 17 digits.
    import math, random, struct
    rng=random.Random(20260913)
    values=[]
    while len(values)<128:
        value=struct.unpack('>d',rng.getrandbits(64).to_bytes(8,'big'))[0]
        if math.isfinite(value):values.append(format(value,'.17e'))
    for pred in ['number_codes','number_chars']:
        source=f'round_trip(N) :- {pred}(N,L),{pred}(M,L),M==N.'
        case('numeric_roundtrip','maplist(round_trip,['+','.join(values)+'])','ok',source)
