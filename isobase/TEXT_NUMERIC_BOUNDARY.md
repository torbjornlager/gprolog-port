# Tested text and numeric boundary

This describes the GNU node's tested behavior and remaining compatibility gaps.
It does not narrow or redefine the ISOBASE conformance target.

## Text

Use UTF-8 encoded HTTP/source and single-quoted atoms for non-ASCII text, for
example `'東京😀'`. The guarded `atom_length/2`, `atom_codes/2`, `atom_chars/2`,
`char_code/2`, `atom_concat/3` and `sub_atom/5` operate on Unicode scalar values,
not UTF-8 bytes. Splits and substring positions never split a multibyte sequence.
Combining characters remain separate scalar values; no normalization or grapheme
clustering is performed. Thus `'é'` has length 2 and `'😀'` has length 1.

`text.pl` encodes/decodes the byte-oriented GNU atom representation. It also
repairs the native printer's escaped continuation bytes before serialization,
while preserving literal backslashes. This applies to HTTP answers, RPC goals,
source transfer and generated native shared source. Malformed UTF-8 encountered
by these paths is rejected rather than emitted as broken text.

Remaining host differences:

- U+0000 is not supported by this atom boundary. Construction raises
  `representation_error(character_code)`. Unicode surrogate values are rejected.
- GNU's lexer is not a Unicode lexer. Quote non-ASCII atoms; arbitrary Unicode
  identifiers, variable names, character-code literal syntax and Unicode escape
  syntax are not promised to match SWI.
- Double-quoted literals are GNU code lists, not SWI string objects. In particular,
  `"abc"` becomes `[97,98,99]`; non-ASCII double-quoted literals retain GNU byte
  semantics. Use quoted atoms and `atom_codes/2` for Unicode code-point lists.
- This is selected mode/error coverage, not exhaustive validation of all modes,
  malformed/cyclic arguments, lexical forms or numeric-to-text conversions.

## Numbers

This 64-bit GNU build's integer range is:

```
-1152921504606846976 .. 1152921504606846975
           -2^60 .. 2^60-1
```

Values inside that range are exact integers. Arithmetic exceeding it raises
catchable `evaluation_error(int_overflow)` in the tested addition, subtraction,
power and shift cases. An out-of-range literal fails during parsing, before the
query's `catch/3` can execute. SWI can instead produce larger exact integers;
this remains a host compatibility gap. No conversion to float is used to hide
integer overflow.

The sampled floating-point operations and errors agree with SWI, including
negative powers (`2^(-1)` yields `0.5`), division by zero, square-root domain
errors and float overflow. `log(0)` now reports `float_overflow` as in SWI.
General cross-host floating-point identity and every arithmetic boundary remain
unaudited. Selected underflow, formatting and round trips are covered below;
NaN/infinity lexical forms remain unsupported.

## Evidence

`boundary_cases.py` contributes Unicode operations, UTF-8 length boundaries,
combining characters, escaped backslashes, selected errors and numeric limits.
The full suite has 253 cases: 244 SWI comparisons, two GNU-only guard checks,
and seven explicit host-boundary assertions. Host-boundary rows retain both
observed responses and an independently specified GNU expectation; they are
not counted as SWI matches.

Compiled tests also cover Unicode shared clauses, clause inspection, RPC answers
and `src_predicates` transfer. Historical performance/memory measurements predate
these wrappers and serialization changes.


## Conversion-mode follow-up

`conversion_mode_cases.py` adds 114 checks for `char_code/2`, `number_codes/2`
and `number_chars/2`. Complete number input lists may use characters or codes;
partially instantiated lists use the selected predicate's output form. The
sampled type/instantiation/syntax errors and their precedence now match SWI.
`1e3` is accepted as `1000.0`; `1e999` raises `syntax_error(float_overflow)`
instead of returning an infinity. Further lexical forms (including digit
separators), formatting and range boundaries remain unaudited or divergent.
After this batch, the full corpus had 425 cases, with host boundaries counted separately.


## Integer-relation follow-up

`between/3` accepts `inf` and `infinite` as upper bounds and enumerates lazily.
Advancing beyond 1152921504606846975 raises `evaluation_error(int_overflow)`;
SWI can continue using bignums. A separate GNU policy test checks this boundary.
The list-mode batch adds ten cyclic-invalid-argument checks that compare error
catchability only: GNU replaces cyclic exception culprits with a finite
`representation_error(cyclic_term)` rather than copying a rational-tree error.


## Numeric lexical and formatting follow-up

The fourth batch adds 236 cases: 220 SWI comparisons and 16 explicit boundary
assertions. `number_codes/2` and `number_chars/2` accept leading `+`, sampled
integer separators (`1_000`, `1 000`, `1_ 000`), prefixed binary/octal/hex integers,
and radix notation such as `16'ff`. Full-token validation rejects malformed
separators. Fractional/exponent separator samples remain syntax errors, as in SWI.
This normalization is confined to number conversions, not the GNU source lexer.

Float output now searches significant-digit precision 1..17 for a spelling that
round-trips to the identical finite binary64 value, preserving signed zero and
adding a decimal point when needed to preserve type. Tests compare selected exact
spellings with SWI and round-trip 128 deterministic binary64 values through each
converter. Subnormal output and underflow to zero are sampled. Exhaustive shortest
format equivalence, locales other than the worker's C locale, and general term
serialization are outside this change.

Explicit GNU expectations in this batch reject out-of-range decimal/hex integers,
`1r2`, `1.0Inf`, `1.5NaN`, fullwidth digits and Arabic-Indic digits with
`syntax_error(illegal_number)`. SWI accepts these samples, so they are counted as
host boundaries, not matching cases. No rational or non-finite value is silently
converted to an ordinary float. The full corpus has 809 cases (23 boundaries).


## Arithmetic-mode follow-up

The seventh batch samples right-to-left arithmetic expression-argument evaluation,
half-away-from-zero rounding (including adjacent binary64 values), zero raised to
a negative power, and signed-zero atan2 quadrants. These now agree with SWI in the
100-case higher-order/arithmetic/template batch. Other arithmetic domain boundaries
and exhaustive floating-point equivalence remain open. Prolog template rendering
now uses list-element precedence, without changing the underlying numeric parser.
