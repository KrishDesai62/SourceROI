"""Read-only analysis of the exposed prior local run; never tunes new policies."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark,scan_sources

ASSESSMENTS = {
'squad-57112686b654c5140001fbd3': ('context_filtering', 'The 512-character whole-chunk filter discarded the relevant Steam_engine passage and retained an unrelated short passage. The published solar answer disappeared. This supports a context-selection failure, not failure of the source corpus.'),
'squad-5725d34089a1e219009abf51': ('scoring_ambiguity', 'The complete reference passage remains supplied. The answer differs as “Provided” versus published “provide”. This is plausibly semantically equivalent; keep the exact-match failure unchanged and flag independent review. There is no evidence of missing information.'),
'hotpot-5a8db19d5542994ba4e3dd00': ('empty_context_and_baseline_support_incomplete', 'The 128-character filter removed every chunk. The baseline contained For Against but not the annotated Local H passage. Removal of available support is observed; the baseline yes answer is not proven fully grounded, and prior knowledge may contribute.'),
'hotpot-5ab859a955429934fafe6d7b': ('empty_context', 'The baseline supplied the box-set and song passages with all supporting facts. The 512-character filter discarded every chunk; Bob Dylan replaced the supported Phil Spector answer. This supports destructive filtering followed by unsupported generation.'),
'squad-57271c235951b619008f860c': ('generation_or_distractor_sensitivity_uncertain', 'Both configurations supplied the apartheid passage. The selected distractors changed and the response became correct. Reduced distraction is plausible, but attention/reasoning variation is not established causally without a controlled follow-up.'),
'hotpot-5a8e068b5542995085b37384': ('correct_without_evidence', 'The new policy supplied no context yet returned yes. This is a reference-score recovery without supplied support, not evidence-selection success. Prior knowledge, question clues or guessing cannot be distinguished here.'),
'hotpot-5ab84bf555429916710eb01f': ('complementary_evidence_retrieved', 'Coverage selection restored both Euromarché and Carrefour, which the baseline missed. Both published supporting articles are now present and the answer becomes correct. This supports a useful ranking/coverage association; it is not a universal causal source-importance score.')}


def main():
    cfg=read_config('workspace/local-llm-96')
    tasks={t['id']:t for t in load_benchmark(cfg)}; chunks={c['id']:c for c in scan_sources(cfg)[1]}
    report=json.loads(Path('docs/artifacts/local-llm-96.json').read_text())
    variants={e['name']:{r['id']:r for r in e['runs'][0]['tasks']} for e in report['experiments'] if e['partition']=='heldout'}
    lost=report['comparisons']['sourceroi'][0]['lost_tasks']; gained=report['comparisons']['sourceroi'][0]['gained_tasks']
    cases=[]; lines=['# Source failure analysis','', 'Read-only analysis of the already exposed 48-question test. No gold answers or scores were changed. These are evidence-backed engineering hypotheses, not independently reviewed semantic judgments.','']
    for tid in lost+gained:
        task=tasks[tid]; before=variants['original'][tid]; after=variants['sourceroi'][tid]
        cause,explanation=ASSESSMENTS[tid]
        case={'id':tid,'outcome':'new_failure' if tid in lost else 'recovery','question':task['question'],
              'accepted_answers':task['accepted_answers'],'baseline_answer':before['actual'],'candidate_answer':after['actual'],
              'classification':cause,'assessment':explanation,'baseline_context':[], 'candidate_context':[], 'reference_evidence':task['evidence']}
        lines += [f"## {case['outcome']}: {tid}",'',task['question'],'',f"Published answers: {json.dumps(task['accepted_answers'],ensure_ascii=False)}",f"Baseline: {before['actual']}",f"SourceROI: {after['actual']}",'',f"Assessment: **{cause}**. {explanation}",'']
        for label,row in [('baseline',before),('candidate',after)]:
            ctx=[chunks[cid] for cid in row['retrieved_chunk_ids']]
            refs=[e for e in task['evidence'] if any(c['document_id']==e['document_id'] and e['quote'] in c['text'] for c in ctx)]
            case[label+'_context']=ctx
            case[label+'_complete_reference_quotes']=len(refs)
            lines += [f"{label.title()} passages ({len(refs)}/{len(task['evidence'])} full reference quotes):",'']
            lines += [f"- {c['title']} — `{c['id']}`" for c in ctx] or ['- No context supplied.']
            lines.append('')
        cases.append(case)
    lines += ['## Implications','', 'Three exact-score losses involve destructive context filtering; one has a plausible tense-only scoring ambiguity. Two recoveries have supplied reference evidence, while one was generated with no context. Do not claim all failures were missing-information failures or all recoveries were grounded.','', 'New policies and baselines must be frozen and tested on new document-disjoint questions. The old cases may be regression tests, never a fresh final test.']
    Path('docs/SOURCE_FAILURE_ANALYSIS.md').write_text('\n'.join(lines)+'\n')
    Path('docs/artifacts/source-failure-analysis.json').write_text(json.dumps({'cases':cases,'independent_semantic_review':'pending'},indent=2)+'\n')
    print('Analyzed',len(cases),'changed outcomes')

if __name__=='__main__': main()
