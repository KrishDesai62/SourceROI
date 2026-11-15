"""Authored adversarial integrity controls + pending external semantic review packet."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.reliability_review import packet,evaluate


def samples():
    def item(name,answer,quote,**metadata):
        return {'id':name,'question':'What is the applicable return period?','answer':answer,'citations':['policy#0'],
            'context':[{'id':'policy#0','text':quote,**metadata}],
            'scope':{'jurisdiction':'US','as_of':'2026-11-13'},'response_contract_valid':True}
    rows=[item('paraphrased_evidence','14 days','Items are eligible for return during the first two weeks following delivery.',jurisdiction='US',effective_from='2026-01-01'),
        item('correct_number_wrong_support','14 days','Warranty coverage lasts 14 days.',jurisdiction='US',effective_from='2026-01-01'),
        item('outdated_policy','30 days','Products may be returned within 30 days.',jurisdiction='US',effective_to='2025-01-01'),
        item('wrong_jurisdiction','30 days','Products may be returned within 30 days.',jurisdiction='EU',effective_from='2026-01-01'),
        item('future_policy','14 days','Products may be returned within 14 days.',jurisdiction='US',effective_from='2027-01-01'),
        item('missing_scope_metadata','14 days','Products may be returned within 14 days.'),
        item('contradictory_claim','30 days','Products may be returned within 14 days.',jurisdiction='US',effective_from='2026-01-01'),
        item('correct_supported_literal','14 days','Products may be returned within 14 days.',jurisdiction='US',effective_from='2026-01-01')]
    unknown=item('fabricated_citation','14 days','Returns are 14 days.');unknown['citations']=['unknown#0'];rows.append(unknown)
    missing=item('no_citation','14 days','Returns are 14 days.');missing['citations']=[];rows.append(missing)
    contract=item('bad_contract','14 days','Returns are 14 days.');contract['response_contract_valid']=False;rows.append(contract)
    return rows


def main(output):
    output=Path(output)
    if output.exists():raise ValueError('Existing evidence')
    data=samples();result={'kind':'semantic_citation_validation','independently_reviewed':False,
      'deterministic_controls':[{'id':s['id'],**evaluate(s)} for s in data],
      'items':[packet(s) for s in data],'semantic_accuracy':None,'citation_entailment_accuracy':None,'model_judgments':0,
      'limitations':'Authored controls test integrity/applicability only. Paraphrase, wrong-support and contradictory claims require external claim adjudication; no semantic verdict is fabricated.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'samples':len(data),'independent_reviews':0,'output':str(output)},indent=2))
    return result

if __name__=='__main__':main(sys.argv[1])
