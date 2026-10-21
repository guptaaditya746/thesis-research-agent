"""CPU-only diagnostic experiments, not product implementation or a benchmark.

Run at repository root with PYTHONPATH=. and the existing environment's Python.
Uses actual term matching and regex-only engine; no model or network calls.
Writes results beside this script. Handwritten expected roles are diagnostic labels.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from evidence.extractors import terms
from evidence.protocol import load
from evidence.tests.conftest import regex_run

HERE = Path(__file__).resolve().parent
REPO = Path.cwd()
PROPOSAL = Path('/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/tests/EV1/diagnostics/proposal/protocol.yaml')


def config(p, kind, name, key):
    return next(e.config[key] for e in p.evidence_types[kind].extractors if e.name == name)


def candidate_role(text):
    """Throwaway phrase-level scope guard; NOT a replacement extractor.

    Only inspect a parenthetical attached immediately to RAG. A retrieval ablation
    is control; an ablation of a component is unresolved/other. No NLP dependency.
    """
    m = re.search(r'\bRAG\s*\(([^)]*)\)', text)
    if m and re.search(r'\b(?:no|without)\s+retrieval\b', m[1], re.I):
        return ['closed_book']
    if m and re.search(r'\b(?:no|without)\b', m[1], re.I):
        return ['other']
    if re.search(r'\bRAG\s+without\s+reranking\b', text):
        return ['other']
    return None  # deliberately abstain outside this tiny supported scope


def main():
    saved = HERE / 'proposal-config.json'
    if saved.exists():
        proposal_config = json.loads(saved.read_text())
    else:
        proposal = load(PROPOSAL)
        proposal_config = {'conditions': config(proposal, 'condition', 'regex_condition', 'conditions'),
                           'metrics': config(proposal, 'metric', 'regex_metric', 'metrics'),
                           'original_proposal_sha256': hashlib.sha256(PROPOSAL.read_bytes()).hexdigest()}
    ps = terms.condition_patterns(proposal_config['conditions'])
    cases = [
        ('RAG (no retrieval)', ['closed_book']),
        ('RAG (without retrieval)', ['closed_book']),
        ('RAG (no reranking)', ['other']),
        ('RAG without reranking', ['other']),
        ('RAG model', ['rag']),
        ('The RAG model is not worse than the closed-book model.', ['rag', 'closed_book']),
        ('The RAG model has no retrieval failures.', ['rag']),
        ('Unlike the RAG model, the baseline uses no retrieval.', ['rag', 'closed_book']),
    ]
    rows = []
    for text, expected in cases:
        actual = [m.key for m in terms.find_all(text, ps)]
        rows.append({'experiment': 'condition_scope', 'input': text, 'expected_roles': expected,
                     'actual_mentions': [{'text': m.text, 'role': m.key} for m in terms.find_all(text, ps)],
                     'matches_expected': actual == expected, 'candidate_only_roles': candidate_role(text)})
    metrics = [tuple(m) for m in proposal_config['metrics']]
    for text in ['FActScore', 'factuality score', 'accuracy', 'factual accuracy']:
        all_hits = [{'canonical': k, 'text': m.group()} for pattern, k, _ in metrics
                    for m in re.finditer(pattern, text)]
        rows.append({'experiment': 'metric_order', 'input': text, 'all_rules_matching': all_hits,
                     'forward': [m.key for m in terms.find_all(text, metrics)],
                     'reversed': [m.key for m in terms.find_all(text, list(reversed(metrics)))]})
    intro = '# Comparison\n\nWe compare a RAG model with a closed-book model.\n\n## Results\n\n'
    layouts = {
        'simple_table': '| System | Factual accuracy (%) |\n|---|---|\n| RAG model | 75 |\n| closed-book model | 60 |\n',
        'transposed_table': '| Metric | RAG model | closed-book model |\n|---|---|---|\n| factual accuracy (%) | 75 | 60 |\n',
        'dataset_first_table': '| Dataset | System | Factual accuracy (%) |\n|---|---|---|\n| Trivia | RAG model | 75 |\n| Trivia | closed-book model | 60 |\n',
        'dataset_last_table': '| System | Factual accuracy (%) | Dataset |\n|---|---|---|\n| RAG model | 75 | Trivia |\n| closed-book model | 60 | Trivia |\n',
        'denominator_prose': 'The RAG model has factual accuracy of 75 out of 100 answers. The closed-book model has factual accuracy of 60 out of 100 answers.\n',
    }
    with tempfile.TemporaryDirectory(prefix='extraction-research-') as tmp:
        for name, body in layouts.items():
            text = intro + body
            answer, items = regex_run({'P': text}, Path(tmp) / name)
            measurements = []
            for item in items.values():
                if item['evidence_type'] == 'measurement':
                    measurements.append({'role': items[item['links']['condition']]['fields']['role'],
                                         **item['fields']})
            expected = [{'role': 'rag', 'value': .75, 'dataset': 'Trivia' if name.startswith('dataset') else None},
                        {'role': 'baseline', 'value': .60, 'dataset': 'Trivia' if name.startswith('dataset') else None}]
            rows.append({'experiment': 'measurement_layout', 'case': name, 'input': text,
                         'expected_measurements': expected, 'actual_measurements': measurements,
                         'matches_expected': sorted(measurements, key=lambda x: x['role']) == sorted(expected, key=lambda x: x['role']),
                         'answer': answer})
    report = {'scope': 'adversarial microcases; not held-out accuracy estimates',
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'proposal_fixture_sha256': proposal_config['original_proposal_sha256'],
              'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                map(Path, ['evidence/extractors/terms.py', 'evidence/extractors/measure.py', 'evidence/engine.py'])},
              'results': rows}
    (HERE / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    # Keep the effective proposal config portable and independent of the sibling worktree.
    saved.write_text(json.dumps(proposal_config, indent=2) + '\n')
    print(json.dumps([{'experiment': r['experiment'], 'input': r.get('input', '')[:50],
                       **{k: r[k] for k in ('case', 'matches_expected', 'forward', 'reversed', 'actual_measurements') if k in r}}
                      for r in rows], indent=2))


if __name__ == '__main__':
    main()
