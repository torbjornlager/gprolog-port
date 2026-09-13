"""Generate a reviewable inventory from the documented /call acceptance rows.
Implementation mappings are explicit; test entry points are not coverage proofs.
"""
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent
CONTRACT=Path('/Users/lager/trinity-demonstrator/docs/WEB_PROLOG_BUILTINS_ACCEPTANCE_MATRIX.md')
def name(text):return text.strip().strip('()').strip("'")
implemented={}
for pred,arity in re.findall(r'iso_pure\((.*?)\/(\d+)\)\.',(ROOT/'policy.pl').read_text()):
    implemented[f'{name(pred)}/{arity}']='policy.pl → GNU built-in'
def add(names,arities,file):
    for n in names.split():
        for arity in arities:implemented[f'{n}/{arity}']=file
add(', ; ->',[2],'policy.pl: native control structure')
add('catch',[3],'policy.pl: native control structure')
add('\\+ once',[1],'policy.pl: guarded control')
add('call',range(1,9),'policy.pl: scoped closure application')
add('findall bagof setof',[3],'policy.pl: guarded all-solutions')
add('clause',[2],'policy.pl + source.pl + compile_shared.pl')
add('phrase',[2,3],'policy.pl: DCG expansion and guarded execution')
add('maplist',range(2,6),'policy.pl: scoped maplist')
add('foldl',range(4,8),'policy.pl: scoped foldl')
add('nth0 nth1',[3,4],'prologue.pl')
add('succ',[2],'prologue.pl')
add('between',[3],'prologue.pl')
add('call_nth length atom_length',[2],'prologue.pl')
implemented['arg/3']='prologue.pl'
add('sort keysort =..',[2],'prologue.pl')
add('term_variables',[2],'policy.pl: independent result unification')
add('time runtime_property throw',[1],'prologue.pl')
add('is =:= =\\= < =< > >=',[2],'prologue.pl: guarded arithmetic')
add('atom_codes atom_chars char_code atom_length',[2],'text.pl')
add('number_codes number_chars',[2],'text.pl + terms.c: guarded conversion')
add('atom_concat',[3],'text.pl')
add('sub_atom',[5],'text.pl')
add('length',[2],'prologue.pl + terms.c: list-spine identity')
add('rpc',[2,3],'rpc.pl + transport.c')
add('promise',[3,4],'rpc.pl + transport.c')
add('yield',[2,3],'rpc.pl + transport.c')
mode_batch={'atom_codes/2','atom_chars/2','atom_length/2','atom_concat/3','sub_atom/5','length/2'}
conversion_batch={'char_code/2','number_codes/2','number_chars/2'}
term_batch={'functor/3','arg/3','=../2','copy_term/2','term_variables/2','compare/3','sort/2','keysort/2','findall/3','bagof/3','setof/3','@</2','@>/2','@=</2','@>=/2','==/2','\\==/2','subsumes_term/2','unify_with_occurs_check/2'}
list_batch={'member/2','append/3','select/3','nth0/3','nth0/4','nth1/3','nth1/4','succ/2','between/3'}
rows=[]
section=CONTRACT.read_text().split('## Ordinary Goal Acceptance',1)[1].split('## Source-Only Acceptance',1)[0]
for line in section.splitlines():
    if not line.startswith('|'):continue
    cells=line.split('|')
    if not cells[2].strip().startswith('yes'):continue
    optional='Local extension' in cells[-2]
    for item in re.findall(r'`([^`]+)`',cells[1]):
        match=re.fullmatch(r'(.*)/(\d+)(?:-(\d+))?',item)
        assert match,item
        n=name(match[1]);start=int(match[2]);end=int(match[3] or match[2])
        for arity in range(start,end+1):
            pi=f'{n}/{arity}'
            assert optional or pi in implemented,pi
            status='optional extension; unavailable' if optional else 'implemented; complete mode audit pending'
            evidence='conformance_tests.py; inspect individual cases'
            if pi in mode_batch:
                status='implemented; selected argument-mode audit complete'
                evidence='predicate_mode_cases.py (bound, partial, invalid arguments; length cycles)'
            elif pi in conversion_batch:
                status='implemented; selected conversion-mode audit complete'
                evidence='conversion_mode_cases.py; numeric_mode_cases.py (selected modes, lexical forms and round trips)'
            elif pi in term_batch:
                status='implemented; selected acyclic term-mode audit complete'
                evidence='term_mode_cases.py (construction, sharing, ordering and all-solutions)'
            elif pi in list_batch:
                status='implemented; selected list-mode audit complete'
                evidence='list_mode_cases.py (remainder, improper/cyclic lists, integer relations)'
            elif n in ('rpc','promise','yield'):evidence='rpc_option_cases.py; rpc_tests.py; https_tests.py; RPC_BOUNDARY.md'
            elif n=='phrase':
                status='implemented; selected DCG-mode audit complete'
                evidence='dcg_mode_cases.py; mode_cases.py; policy_tests.py'
            elif n in ('maplist','foldl','call'):evidence='mode_cases.py; higher_arithmetic_cases.py; policy_tests.py; source_tests.py'
            elif n=='clause':evidence='shared_db_tests.py; compiled_tests.py; proof_tree_tests.py'
            elif n in ('char_code','number_chars','number_codes'):evidence='boundary_cases.py; conformance_tests.py; mode audit pending'
            if optional:evidence='acceptance matrix: local extension, not required prologue'
            rows.append(dict(predicate=pi,scope='optional' if optional else 'required',implementation=implemented.get(pi,'unavailable'),status=status,evidence=evidence,remaining='All unsampled modes, error precedence, determinism and source interactions'))
assert len({r['predicate'] for r in rows})==len(rows)
(ROOT/'predicate-inventory.json').write_text(json.dumps(rows,indent=2)+'\n')
required=sum(r['scope']=='required' for r in rows)
lines=['# ISOBASE predicate checklist','',f'The acceptance matrix lists **{required} required callable predicate/arities** and one optional extension. Arity ranges are expanded below.','',
       'Generated by `python3 predicate_inventory.py` from the documented `/call` rows. Implementation mappings are explicit and generation fails on an unmapped required entry. Test references identify places to inspect; they are **not** evidence that every mode is covered. No predicate is marked fully conformant.','',
       '| Predicate | Implementation | Audit status | Evidence entry point |',
       '| --- | --- | --- | --- |']
for r in rows:lines.append(f"| `{r['predicate']}` | {r['implementation']} | {r['status']} | {r['evidence']} |")
lines+=['','## Separate obligations','',
    '- Source directives: `dynamic/1`, `multifile/1`, `discontiguous/1`; declaration behavior and source isolation tests exist.',
    '- DCG source syntax: alternatives, conjunction, cuts, embedded goals and remainder lists are sampled; variable grammar bodies, remaining constructs and malformed source need further audit.',
    '- Arithmetic expression functors: see the contract sections 9.1, 9.3 and 9.4; boundary_cases.py samples them, not every numeric mode.',
    '- Source options and HTTP behavior: separately tracked in CONFORMANCE.md and RPC_BOUNDARY.md.',
    '- Text/numeric/host differences: TEXT_NUMERIC_BOUNDARY.md. Cyclic list-spine errors still use a finite GNU representation error; the cycle test compares catchability, not the exact SWI error term.',
    '', '## First mode-audit batch','',
    '`predicate_mode_cases.py` contains 58 cases. The initial run had 18 discrepancies. The fixes cover bound text arguments, numeric text coercion, error categories/precedence, partial output lists, length aliases and finite lists with cyclic elements. These are selected modes, not an exhaustive ISO test suite.',
    '', '## Second mode-audit batch','',
    '`conversion_mode_cases.py` contains 114 cases. The first 96 exposed 45 discrepancies, now corrected. Eighteen additional lexical checks cover signed/decimal exponents, invalid suffixes and overflow. Complete input lists can use characters or codes; partial lists preserve each predicate’s output representation. Infinity from native parsing is rejected with the sampled SWI float-overflow error.',
    '', '## Third mode-audit batch','',
    '`list_mode_cases.py` contains 148 cases. The initial 127 exposed six discrepancies in succ/2 and between/3, now corrected. The batch covers remainder modes, improper lists, bounded access to cyclic spines, infinite upper bounds and cyclic invalid arguments. Ten cyclic-error cases compare catchability only; GNU uses a finite representation error. Infinite range enumeration raises int_overflow at the native integer boundary; no bignum equivalence is claimed.',
    '', '## Fourth mode-audit batch','',
    '`numeric_mode_cases.py` adds 236 checks: 220 SWI comparisons and 16 explicit host-boundary assertions. Numeric conversions accept the sampled leading plus signs, integer separators and radix forms. Float output chooses a round-trip spelling using increasing significant-digit precision. The tests include 128 deterministic binary64 values through each converter. Unsupported bignums, rationals, non-finite lexical forms and sampled Unicode digits remain explicit gaps; this does not change the source lexer or establish exhaustive float-format equivalence.',
    '', '## Fifth mode-audit batch','',
    '`term_mode_cases.py` adds 174 SWI comparisons. The initial 124 exposed 19 discrepancies, corrected by independent output-list unification and input/error-order wrappers. The samples cover term construction/decomposition, variable sharing, ordering, sorting, all-solutions grouping and exception timing. Full rational-tree behavior, attributed variables and exhaustive choicepoint/determinism checks remain open.',
    '', '## Sixth mode-audit batch','',
    '`dcg_mode_cases.py` adds 75 checks for grammar bodies, input/remainder modes, variable grammars, cuts, alternatives, pushback, embedded goals and invalid source. Ten rejection cases compare rejection only. GNU now handles the empty embedded goal {} and aligns open terminal-list errors. A demonstrator grammar-closure bug was fixed in control_guard.pl; grammar translation precedes guarded ordinary execution. Full DCG syntax (including soft cut), rational trees and all module/context combinations remain open.',
    '', '## Seventh mode-audit batch','',
    '`higher_arithmetic_cases.py` adds 100 SWI comparisons. The initial 75 exposed four arithmetic differences and a Prolog response precedence bug. The fixes cover right-to-left expression-argument evaluation, half-away-from-zero rounding, zero raised to a negative power, signed-zero atan2 and list-element serialization of templates. Higher-order aliasing, mismatched lists, empty lists and grammar closures are sampled; this is not exhaustive context or arithmetic coverage.',
    '', '## Eighth mode-audit batch','',
    '`rpc_option_cases.py` adds 61 checks using one disposable GNU target for both clients: 59 SWI comparisons and two timeout-policy boundaries. Samples cover duplicate options, variable-valued once/timeout, source composition, exports, isolation and promise offsets/templates. GNU now treats unbound remote timeout as omitted and aligns sampled once binding; SWI source composition now preserves option order as documented. Negative timeouts remain rejected by GNU. URI aliases, unknown options, all validation-order combinations and transport limits remain open.',
    '', '## Next batches','',
    '1. Remaining RPC URI forms, validation-order combinations and transport-option boundaries.',
    '2. Remaining higher-order/DCG module contexts and arithmetic boundaries.',
    '3. Extend term/rational-tree and numeric coverage beyond the selected samples and resolve the documented host boundaries.', '']
(ROOT/'PREDICATE_CHECKLIST.md').write_text('\n'.join(lines))
print(f'Inventory: {required} required entries, {len(rows)-required} optional; no complete-conformance claims')
