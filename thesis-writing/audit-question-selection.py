"""Run from repository root: PYTHONPATH=backend .venv/bin/python thesis-writing/audit-question-selection.py.
Reads existing data only; writes its derived audit beside this script. Makes no model calls.
"""
from pathlib import Path
import json
from evaluation.cli import _real_questions
from evaluation.wholerun import question_papers, tune_papers

base = Path('/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-general/real')
campaign = Path('/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis-campaign-20261106T132128Z')
result = {}
for name in ['scilead', 'scirex']:
    root = base/name
    src = root if name == 'scilead' else root/'test.jsonl'
    source_questions = _real_questions(name, src, None)
    questions = _real_questions(name, src, root/'corpus')
    ids = json.loads((campaign/f'scores/sample-10-corrected/{name}/sample.json').read_text())['ids']
    chosen = [q for q in questions if q.id in ids]
    assert len(chosen) == 10
    assert all(not(set(question_papers(q)) & tune_papers(q)) for q in chosen)
    for q in chosen:
        for mode in ['global', 'per_paper']:
            baseline = json.loads((campaign/f'real-v1/scores/{name}-v2/rag-answers/{mode}/{q.id}.json').read_text())
            assert baseline['question'] == q.question
        plan = campaign/f'real-v1/runs/{name}/auto-confirmed/on/{q.id}/plan.json'
        if plan.exists():
            assert json.loads(plan.read_text())['question'] == q.question
    result[name] = {'source_only_questions': len(source_questions), 'corpus_filtered_questions': len(questions),
                    'sample_ids': ids, 'sample_paper_guard_passed': True,
                    'question_texts_match_baselines_and_executed_plans': True}
Path(__file__).with_name('question-selection-audit.json').write_text(json.dumps(result, indent=2)+'\n')
print('Both ten-question samples pass paper guards and match persisted question texts.')
