% Unicode scalar operations over GNU's byte-oriented atom storage.
% Keep UTF-8 encoding at the boundary; never split a multibyte sequence.
iso_atom_unicode(A,Codes) :-
    (number(A)->number_codes(A,Codes)
    ;acyclic_term(A)->atom_codes(A,Bytes),iso_utf8_decode(Bytes,Codes)
    ;throw(error(representation_error(cyclic_term),atom_codes/2))).
iso_text_codes(A,Codes) :- iso_text_list(A,Codes,codes).
iso_text_chars(A,Chars) :- iso_text_list(A,Chars,chars).
iso_text_list(A,List,Output) :-
    iso_spine_kind(List,Kind),
    (Kind==cyclic->throw(error(representation_error(cyclic_term),atom_codes/2));true),
    iso_read_text_list(List,List,first,State,Given),
    (State==complete ->
        (nonvar(A)->iso_atom_unicode(A,Actual),Actual=Given
        ;iso_utf8_encode(Given,Bytes),atom_codes(A,Bytes))
    ;var(A)->throw(error(instantiation_error,atom_codes/2))
    ;iso_atom_unicode(A,Actual),
     (Output==codes->List=Actual;iso_codes_chars(Actual,Chars),List=Chars)).

% SWI accepts a complete character list or code list in either conversion.
% A variable element/tail switches to output mode without inspecting later data.
iso_read_text_list(L,Original,Mode,State,Codes) :-
    (var(L)->State=partial
    ;L=[]->State=complete,Codes=[]
    ;L=[C|Cs]->
        (var(C)->State=partial
        ;iso_text_element_mode(Mode,C,Next),iso_text_element(Next,C,Code),
         Codes=[Code|Rest],iso_read_text_list(Cs,Original,Next,State,Rest))
    ;iso_throw(error(type_error(list,Original),atom_codes/2))).
iso_text_element_mode(first,C,Mode) :- !,
    (atom(C),iso_atom_unicode(C,[_])->Mode=chars;Mode=codes).
iso_text_element_mode(Mode,_,Mode).
iso_text_element(chars,C,Code) :-
    (atom(C),iso_atom_unicode(C,[Code])->true
    ;iso_throw(error(type_error(character,C),atom_chars/2))).
iso_text_element(codes,C,C) :-
    (integer(C)->iso_unicode_code(C)
    ;iso_throw(error(type_error(character_code,C),atom_codes/2))).
iso_codes_chars([],[]).
iso_codes_chars([C|Cs],[A|As]) :- iso_text_char_code(A,C),iso_codes_chars(Cs,As).
iso_text_char_code(A,C) :-
    (nonvar(A) ->
        (atom(A),iso_text_codes(A,[Code])->true
        ;iso_throw(error(type_error(character,A),char_code/2))),
        (nonvar(C)->iso_unicode_code(C);true),C=Code
    ;iso_unicode_code(C),iso_text_codes(A,[C])).
iso_unicode_code(C) :-
    (var(C) -> throw(error(instantiation_error,char_code/2))
    ;\+integer(C) -> throw(error(type_error(integer,C),char_code/2))
    ;C<0 -> throw(error(type_error(character_code,C),char_code/2))
    ;C>0,C=<1114111,\+ (C>=55296,C=<57343) -> true
    ;throw(error(representation_error(character_code),char_code/2))).
iso_text_length(A,N) :-
    iso_atom_unicode(A,Codes),length(Codes,Actual),
    (nonvar(N)->iso_integer(N);true),N=Actual.
iso_text_concat(A0,B0,C0) :-
    iso_text_scalar(A0,A),iso_text_scalar(B0,B),iso_text_scalar(C0,C),
    iso_text_concat_atoms(A,B,C).
iso_text_scalar(A,B) :-
    (number(A)->number_codes(A,C),atom_codes(B,C);B=A).
iso_text_concat_atoms(A,B,C) :-
    (nonvar(C),atom(C) ->
        iso_text_codes(C,Codes),
        (nonvar(A) -> iso_text_codes(A,As);true),
        (nonvar(B) -> iso_text_codes(B,Bs);true),
        append(As,Bs,Codes),iso_text_codes(A,As),iso_text_codes(B,Bs)
    ;atom_concat(A,B,C)).
iso_text_sub(A,Before,Length,After,Sub) :-
    (var(A) -> throw(error(instantiation_error,sub_atom/5));true),
    iso_text_codes(A,Codes),
    iso_text_index(Before),iso_text_index(Length),iso_text_index(After),
    (nonvar(Sub) -> iso_text_codes(Sub,Part),length(Part,Length);true),
    length(Codes,Size),between(0,Size,Before),Remaining is Size-Before,
    between(0,Remaining,Length),After is Remaining-Length,
    length(Prefix,Before),append(Prefix,Tail,Codes),length(Part,Length),
    append(Part,_,Tail),iso_text_codes(Sub,Part).
iso_text_index(N) :-
    (var(N) -> true
    ;\+integer(N) -> throw(error(type_error(integer,N),sub_atom/5))
    ;N>=0 -> true
    ;throw(error(domain_error(not_less_than_zero,N),sub_atom/5))).

iso_utf8_decode([],[]).
iso_utf8_decode([B|Bs],[C|Cs]) :-
    (B>0,B<128 -> C=B,Rest=Bs
    ;B>=194,B=<223,Bs=[B2|Rest],iso_cont(B2) -> C is (B-192)*64+B2-128
    ;B>=224,B=<239,Bs=[B2,B3|Rest],iso_cont(B2),iso_cont(B3),
       (B=:=224 -> B2>=160;true),(B=:=237 -> B2<160;true) ->
       C is (B-224)*4096+(B2-128)*64+B3-128
    ;B>=240,B=<244,Bs=[B2,B3,B4|Rest],iso_cont(B2),iso_cont(B3),iso_cont(B4),
       (B=:=240 -> B2>=144;true),(B=:=244 -> B2<144;true) ->
       C is (B-240)*262144+(B2-128)*4096+(B3-128)*64+B4-128
    ;throw(error(representation_error(utf8),atom_codes/2))),
    iso_utf8_decode(Rest,Cs).
iso_cont(B) :- B>=128,B=<191.
iso_utf8_encode(L,Bytes) :-
    (var(L) -> throw(error(instantiation_error,atom_codes/2))
    ;L=[] -> Bytes=[]
    ;L=[C|Cs] -> iso_unicode_code(C),iso_utf8_char(C,Bytes,Tail),iso_utf8_encode(Cs,Tail)
    ;throw(error(type_error(list,L),atom_codes/2))).
iso_utf8_char(C,[C|Tail],Tail) :- C<128,!.
iso_utf8_char(C,[B1,B2|Tail],Tail) :- C<2048,!,
    B1 is 192+C//64,B2 is 128+C mod 64.
iso_utf8_char(C,[B1,B2,B3|Tail],Tail) :- C<65536,!,
    B1 is 224+C//4096,B2 is 128+(C//64) mod 64,B3 is 128+C mod 64.
iso_utf8_char(C,[B1,B2,B3,B4|Tail],Tail) :-
    B1 is 240+C//262144,B2 is 128+(C//4096) mod 64,
    B3 is 128+(C//64) mod 64,B4 is 128+C mod 64.

% GNU's quoted printer escapes some UTF-8 continuation bytes as \xHH\.
% Undo only high-byte escapes, preserving doubled backslashes verbatim, then
% validate the resulting UTF-8 before it is placed on the wire or in source.
iso_write_text(Term,Options,Text) :-
    (acyclic_term(Term)->true;throw(error(representation_error(cyclic_term),serialization))),
    write_term_to_atom(Raw,Term,Options),atom_codes(Raw,Bytes),
    iso_unescape_utf8(Bytes,Fixed),iso_utf8_decode(Fixed,_),atom_codes(Text,Fixed).
iso_unescape_utf8([],[]).
iso_unescape_utf8([92,92|Bs],[92,92|Cs]) :- !,iso_unescape_utf8(Bs,Cs).
iso_unescape_utf8([92,120,H,L,92|Bs],[B|Cs]) :-
    iso_hex(H,X),iso_hex(L,Y),B is X*16+Y,B>=128,!,iso_unescape_utf8(Bs,Cs).
iso_unescape_utf8([B|Bs],[B|Cs]) :- iso_unescape_utf8(Bs,Cs).
iso_hex(C,N) :- C>=48,C=<57,!,N is C-48.
iso_hex(C,N) :- C>=97,C=<102,N is C-87.
iso_render_canonical(Term,Text) :-
    (acyclic_term(Term)->Printable=Term
    ;Printable=error(representation_error(cyclic_term),serialization)),
    iso_write_text(Printable,[quoted(true),ignore_ops(true)],Text).


% Numeric conversions keep their declared character/code representation in
% both directions (contract 0.2.0). Keep numeric argument validation first.
iso_number_text(N,List,Output) :-
    (var(N)->true;number(N)->true;iso_throw(error(type_error(number,N),number_codes/2))),
    iso_spine_kind(List,Kind),
    (Kind==cyclic->throw(error(representation_error(cyclic_term),number_codes/2));true),
    iso_read_text_list(List,List,Output,State,Codes),
    (State==complete->iso_parse_number(Codes,Value),N=Value
    ;var(N)->throw(error(instantiation_error,number_codes/2))
    ;iso_number_output(N,Actual),
      (Output==codes->List=Actual;iso_codes_chars(Actual,Chars),List=Chars)).
:- foreign(iso_finite_number(term)).
:- foreign(iso_float_codes(term,term)).
iso_number_output(N,C) :- (float(N)->iso_float_codes(N,C);number_codes(N,C)).
iso_parse_number(Codes,Value) :-
    iso_numeric_leading(Codes,Trimmed),
    (iso_integer_lexical(Trimmed,Sign,Base,Digits)->
        catch(iso_radix_value(Digits,Base,Sign,0,Value),error(evaluation_error(int_overflow),_),
              throw(error(syntax_error(illegal_number),number_codes/2)))
    ;iso_numeric_plus(Trimmed,Unsigned),
     iso_number_exponent(Unsigned,Normalized),iso_utf8_encode(Normalized,Bytes),
    catch(number_codes(Value,Bytes),error(syntax_error(_),_),
          throw(error(syntax_error(illegal_number),number_codes/2)))),
    (iso_finite_number(Value)->true
    ;throw(error(syntax_error(float_overflow),number_codes/2))).
% GNU requires a decimal point before an exponent. Only rewrite a validated
% decimal integer mantissa and exponent; leave other lexical forms to GNU.
iso_number_exponent(Codes,Normalized) :-
    append(Mantissa,[E|Exponent],Codes),member(E,[101,69]),
    iso_decimal_mantissa(Mantissa),iso_signed_digits(Exponent),!,
    append(Mantissa,[46,48,E|Exponent],Normalized).
iso_number_exponent(Codes,Codes).
iso_decimal_mantissa([W|Cs]) :- member(W,[9,10,11,12,13,32]),!,iso_decimal_mantissa(Cs).
iso_decimal_mantissa(Cs) :- iso_signed_digits(Cs).
iso_signed_digits([S|Cs]) :- member(S,[43,45]),!,iso_digits(Cs).
iso_signed_digits(Cs) :- iso_digits(Cs).
iso_digits([C|Cs]) :- C>=48,C=<57,iso_digit_tail(Cs).
iso_digit_tail([]).
iso_digit_tail([C|Cs]) :- C>=48,C=<57,iso_digit_tail(Cs).

% Recognize the whole integer token before removing separators. Fraction and
% exponent separators remain invalid; malformed tokens fall through unchanged.
iso_numeric_leading([W|Cs],Rest) :- member(W,[9,10,11,12,13,32]),!,iso_numeric_leading(Cs,Rest).
iso_numeric_leading(Cs,Cs).
iso_numeric_plus([43,D|Cs],[D|Cs]) :- D>=48,D=<57,!.
iso_numeric_plus(Cs,Cs).
iso_integer_lexical(Cs,Sign,Base,Digits) :-
    iso_integer_sign(Cs,Sign,Unsigned),iso_integer_base(Unsigned,Base,Body),
    iso_radix_digits(Body,Base,Digits).
iso_integer_sign([45|Cs],-1,Cs) :- !.
iso_integer_sign([43|Cs],1,Cs) :- !.
iso_integer_sign(Cs,1,Cs).
iso_integer_base([48,120|Cs],16,Cs) :- !.
iso_integer_base([48,111|Cs],8,Cs) :- !.
iso_integer_base([48,98|Cs],2,Cs) :- !.
iso_integer_base(Cs,Base,Body) :-
    append(Prefix,[39|Body],Cs),iso_digits(Prefix),
    % Radix prefixes have no separators and must be in 2..36.
    iso_small_base(Prefix,0,Base),Base>=2,Base=<36,!.
iso_integer_base(Cs,10,Cs).
iso_small_base([],N,N).
iso_small_base([C|Cs],N,Base) :- Next is N*10+C-48,Next=<36,iso_small_base(Cs,Next,Base).
iso_radix_digits([C|Cs],Base,[D|Ds]) :-
    iso_radix_digit(C,D),D<Base,iso_radix_tail(Cs,Base,Ds).
iso_radix_tail([],_,[]).
iso_radix_tail([95|Cs],Base,Ds) :- !,iso_numeric_leading(Cs,Rest),iso_radix_digits(Rest,Base,Ds).
iso_radix_tail([32|Cs],Base,Ds) :- !,iso_radix_digits(Cs,Base,Ds).
iso_radix_tail(Cs,Base,Ds) :- iso_radix_digits(Cs,Base,Ds).
iso_radix_digit(C,D) :- C>=48,C=<57,!,D is C-48.
iso_radix_digit(C,D) :- C>=97,C=<122,!,D is C-87.
iso_radix_digit(C,D) :- C>=65,C=<90,D is C-55.
iso_radix_value([],_,_,N,N).
iso_radix_value([D|Ds],Base,Sign,N,Value) :-
    Next is N*Base+Sign*D,iso_radix_value(Ds,Base,Sign,Next,Value).
