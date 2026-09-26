"""Check that every frozen boundary has a disposition and no required probe is waived."""
import json
from comparison_config import ROOT, CONTRACT_DIR, verify_contract

def validate(decisions=None):
    contract=verify_contract()
    document=json.loads((CONTRACT_DIR/'boundary-decisions.json').read_text())
    assert document['contract_version']==contract['version']
    rows=document['decisions'] if decisions is None else decisions
    observations=json.loads((ROOT/'status-evidence.json').read_text())['boundary_observations']
    assert [d['id'] for d in rows]==[f'B{i:02}' for i in range(1,43)],'Missing or duplicate boundary ID'
    keys=lambda rows,goal,template:[(d['family'],d[goal],d[template]) for d in rows]
    assert keys(rows,'original_goal','original_template')==keys(observations,'goal','template'),'Boundary observation identity drift'
    allowed={'shared_requirement','implementation_limit','character_domain_limit','optional_extension'}
    for row in rows:
        assert row['disposition'] in allowed,'Unknown disposition'
        assert all(row[k] for k in ('change','work','basis','policy')),'Incomplete disposition'
        assert bool(row['probe'])==(row['disposition']=='shared_requirement'),'Required probe missing or scope mismatch'
    selection=json.loads((CONTRACT_DIR/'iso-test-selection.json').read_text())
    assert selection['contract_version']==contract['version']
    cases=selection['cases'];ids=[c['id'] for c in cases]
    assert len(ids)==len(set(ids))==10,'Selection identity drift'
    sources={s['url'] for s in selection['sources']}
    assert all(c['source'] in sources and c['source_row'] and c['goal'] and c['expected'] for c in cases)
    return rows

if __name__=='__main__':
    rows=validate()
    print(f'{len(rows)} dispositions validated; required probes cannot be waived')
