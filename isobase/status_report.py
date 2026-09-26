"""Validate reconciliation inputs and render the current status entry point."""
import argparse
import json
from pathlib import Path
import re
from comparison_config import ROOT, verify_contract

def render():
    contract=verify_contract()
    inventory=json.loads((ROOT/'predicate-inventory.json').read_text())
    registry=json.loads((ROOT/'status-obligations.json').read_text())
    evidence=json.loads((ROOT/'status-evidence.json').read_text())
    assert registry['contract_version']==contract['version']
    for scope,key in [('required','required_predicates'),('optional','optional_predicates')]:
        actual=[r['predicate'] for r in inventory if r['scope']==scope]
        assert len(set(actual))==len(actual) and set(actual)==set(contract[key]),f'{scope} mapping drift'
    obligations=registry['obligations'];ids=[r['id'] for r in obligations]
    assert len(ids)==len(set(ids)),'Duplicate obligation IDs'
    assert set(next(r for r in obligations if r['id']=='source-directives')['items'])==set(contract['source_directives'])
    for row in inventory:
        for name in re.findall(r'[\w-]+\.(?:pl|c|h|py)',row['implementation']+' '+row['evidence']):
            assert (ROOT/name).is_file(),f'Missing predicate mapping file: {name}'
    checklist=(ROOT/'RELEASE_CHECKLIST.md').read_text()
    decisions=set(contract['open_decisions'])|set(re.findall(r'\*\*([CSKV]\d\d) —',checklist))
    for row in obligations:
        assert row['items'] and row['implementation'] and row['evidence'] and row['remaining'],row['id']
        for name in row['implementation']+row['evidence']:assert (ROOT/name).is_file(),f'Missing obligation mapping file: {name}'
        assert set(row['decision'].split())<=decisions,row['decision']
    native={name.strip().strip('()').strip("'")+'/'+arity for name,arity in re.findall(r'iso_pure\((.*?)\/(\d+)\)\.',(ROOT/'policy.pl').read_text())}
    extra=set(next(r for r in obligations if r['id']=='gnu-extensions')['items'])
    assert native-set(contract['required_predicates'])-set(contract['optional_predicates'])<=extra,'Unrecorded native callable extension'
    assert evidence['total']==evidence['comparison_cases']+evidence['gnu_guard_cases']+evidence['boundary_cases']
    assert evidence['passed']+len(evidence['failures'])==evidence['total']
    assert len(evidence['boundary_observations'])==evidence['boundary_cases']
    from boundary_decisions import validate
    boundary_rows=validate()
    targeted=json.loads((ROOT/'boundary-evidence.json').read_text())
    assert targeted['contract_version']==contract['version']
    selection=json.loads((ROOT/'contracts'/contract['version']/'iso-test-selection.json').read_text())
    required_ids={r['id'] for r in boundary_rows if r['probe']}|{r['id'] for r in selection['cases']}
    result_ids=[(r['implementation'],r['id']) for r in targeted['results']]
    assert len(result_ids)==len(set(result_ids)) and set(result_ids)=={(host,key) for host in ('gnu','swi') for key in required_ids},'Incomplete targeted evidence'
    assert all(isinstance(row['pass'],bool) for row in targeted['results']),'Unscored required evidence'
    scores={host:sum(row['pass'] for row in targeted['results'] if row['implementation']==host) for host in ('gnu','swi')}
    def links(names):return ', '.join(f'[{n}]({n})' for n in names)
    def cell(text):return text.replace('|','\\|').replace('\n',' ')
    lines=['# Current ISOBASE reconciliation status','',
        'This is the current status entry point. Generated from `status-obligations.json`,',
        '`predicate-inventory.json`, saved evidence and contract decisions; run `make status-check`',
        'to detect mapping or generated-file drift. Update inputs deliberately, then',
        'run `python3 status_report.py` to regenerate. This is an audit index, not',
        'a replacement contract or a claim that every mode has been tested.','',
        f'Contract: **{contract["version"]} (draft)**. Authority: applicable ISO requirements',
        'and explicit shared ISOBASE decisions. SWI is a comparison implementation.',
        'Either node, both, or the contract/tests may need changes. C03 creates the',
        'mapping; C04 settles the 42 dispositions. Implementation work remains in K01–K11.','',
        '## Evidence and confidence','',
        f'- Historical contract {evidence["contract_version"]} run ({evidence["recorded"]}): **{evidence["passed"]}/{evidence["total"]}**, including 42 GNU-specific outcomes in the old score.',
        f'- Categories: {evidence["comparison_cases"]} reference comparisons, {evidence["boundary_cases"]} explicit GNU boundaries,',
        f'  and {evidence["gnu_guard_cases"]} GNU-only guards. Some comparisons establish only rejection/catchability.',
        '- Current comparison accounting leaves those 42 observations unscored; they cannot waive required behavior.',
        f'- Contract 0.2.0 targeted checks: **GNU {scores["gnu"]}/39; SWI {scores["swi"]}/39**. These cover 29 boundary requirements and ten selected TU Wien tests.',
        '- The 13 limit/extension dispositions are not counted as passes. Required failures remain failures.',
        '- Full targeted outcomes and run provenance: [boundary-evidence.json](boundary-evidence.json).',
        f'- Current broad comparison: **{targeted["comparison_run"]["passed"]}/{targeted["comparison_run"]["scored"]}**; 42 unscored observations. 31 disagreements follow the GNU numeric corrections; RPC `limit(0)` also remains unresolved (D01/K01).',
        '- C01 separately ran seven pinning tests and six independent assertions.',
        '  Local/compiled/security/HTTPS/endurance successes reported in SECURITY.md',
        '  are historical evidence, not new executions during this reconciliation.',
        '- The RPC suite stops at its zero-limit assertion, so its later checks',
        '  cannot be described as passing in the current run merely because they exist.',
        '- No required predicate has exhaustive mode coverage or an independently',
        '  completed ISO-clause audit. Mapping a test file is not proof of coverage.',
        '- Saved revisions, result digest, failing case and all 42 boundary observations',
        '  are retained in [status-evidence.json](status-evidence.json). They are observations,',
        '  interpreted by the current contract dispositions. New results must be reconciled explicitly.','',
        '## Required predicates and exclusions','',
        'All **97 required predicate/arities** and the one optional `crypto_data_hash/3`',
        'entry match both contract 0.2.0 and its pinned acceptance snapshot. Each',
        'required predicate has an implementation and evidence entry in',
        '[PREDICATE_CHECKLIST.md](PREDICATE_CHECKLIST.md). Optional hashing is unavailable;',
        'it is not a missing required ISOBASE predicate. Actors, sessions, general I/O',
        'and runtime mutation remain outside the restricted callable profile.',
        'The generator now fails if the snapshot inventory and contract sets diverge.','',
        'The frozen source snapshot is evidence about the pinned Trinity implementation.',
        'It must not silently override a future independently agreed contract version.','',
        '## Non-predicate obligations','',
        '| Obligation / items | Current implementation and evidence | Open decision / remaining work |',
        '| --- | --- | --- |']
    for row in obligations:
        items=', '.join('`'+cell(x)+'`' for x in row['items'])
        lines.append(f'| **{row["id"]}**: {items} | {cell(row["status"])}. Implementation: {links(row["implementation"])}. Evidence entry points: {links(row["evidence"])}. | {row["decision"]}: {cell(row["remaining"])} |')
    lines += ['', 'Arithmetic items above are enumerated from the pinned Trinity builtin catalog',
        f'(`{registry["catalog_provenance"]["repository_commit"]}`). The source path and digest',
        'are in status-obligations.json. This enumerates the audit surface without',
        'declaring every listed functor an ISO requirement or claiming the GNU evaluator',
        'rejects every unlisted expression. DCG, option and wire rows are separate',
        'obligations; counting them as callable predicates would misstate coverage.','',
        '## Disagreement register and responsibility','',
        '| Issue | Evidence / classification | Next owner/action |','| --- | --- | --- |',
        '| RPC limit(0) | Recorded failure: SWI raises a positive-integer error; GNU returns failure. | D01/K01: shared API decision, then change the affected node(s) and tests. No presumption GNU is wrong. |',
        '| 23 numeric/text boundary cases | Seven host_boundary and 16 numeric_lexical observations, including range, strings, NUL and numeric lexical forms. | C04 decided portable ranges, float power, codes and lexical policy. K02/K03 implement and audit remaining modes; GNU float power and numeric character/code distinction are corrected with independent regressions; the pinned SWI adapter still fails these requirements. |',
        '| 19 RPC option/address boundary cases | Two rpc_option_modes plus seven options, seven URI and three alias observations. | GNU now passes all 29 boundary requirements, including address errors before source I/O; SWI corrections and broader K05–K07 audits remain open. |',
        '| Cyclic terms/errors, capabilities and asynchronous cleanup | Broader differences described in TEXT_NUMERIC_BOUNDARY.md and RPC_BOUNDARY.md; not all are among the 42 expected-GNU rows. | D04/D05/V01: separate valid host capabilities from required semantics and deliberately safer cleanup. |',
        '| Extra callable surface | GNU exposes nth/3 and promise_cleanup/1 outside the contract inventory. Targeted worker probes are stored in status-evidence.json. | C04: retain documented GNU-local extensions; K06/K07 still govern shared API and cleanup. |',
        '| rpc/3 template and offset | Code inspection: common GNU validator accepts both; rpc builds its own variable template and starts at offset zero. Pinned catalog describes these as promise-only. | D05/K06: verify both peers with dedicated cases and choose rejection or an explicit extension. Current evidence is inspection, not a new differential result. |',
        '| Authentication, network access, resource limits | Local owner auth, outbound origin/IP restrictions and scoped HTTPS RPC credentials exist; OS/network isolation and credential lifecycle review remain unfinished. | D07/S01–S16: implementation controls governed by THREAT_MODEL.md, not conformance to unsafe peer behavior. |',
        '| Historic reference defects | Prior ledger reports call_nth guarding, grammar-closure and source-composition fixes. These reports are history, not current additional failing cases. | Preserve regression coverage; reopen only with reproducible current evidence. |',
        '| Stale docs | Redirects described as absent; zero limits described as current SWI agreement; auth described as wholly missing; obsolete counts presented as current. | GNU project documentation: corrected by C03. Runtime behavior and locked contract unchanged. |','',
        '## Reading the other documents','',
        '- [CONFORMANCE.md](CONFORMANCE.md): historical audit narrative and test methodology.',
        '- [RPC_BOUNDARY.md](RPC_BOUNDARY.md) and [TEXT_NUMERIC_BOUNDARY.md](TEXT_NUMERIC_BOUNDARY.md): detailed behavior and limits; historical batch counts are labelled.',
        '- [SECURITY.md](SECURITY.md), [THREAT_MODEL.md](THREAT_MODEL.md) and [MEMORY_LIMITS.md](MEMORY_LIMITS.md): controls and deployment assumptions.',
        '- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md): outstanding work and completion criteria.',
        '- [contracts/0.2.0/CONTRACT.md](contracts/0.2.0/CONTRACT.md): active draft decisions, portable restrictions and implementation responsibilities.','']
    return '\n'.join(lines)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    content=render();path=ROOT/'STATUS.md'
    if args.check:
        if not path.exists() or path.read_text()!=content:raise SystemExit('Stale STATUS.md; run status_report.py')
    else:path.write_text(content)
    print('Status mappings verified: required/optional predicates, source directives, non-predicate obligations and saved evidence')
