#!/usr/bin/env python3
"""Build the standalone evaluation dashboard from EV2 reports; no dependencies."""
import argparse
import datetime
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ev', type=Path, default=root / 'tests/EV2')
args = parser.parse_args()
ev = args.ev.resolve()
methods = {'regex-only': 'Regex only', 'cascade': 'Regex + LLM (all)', 'cascade-gaps': 'Fill gaps — reject lexical misses', 'cascade-gaps-escalate': 'Fill gaps — escalate lexical misses', 'agentic': 'With agent extractor', 'agentic-gaps': 'With agent — fill gaps'}
reports = []
for method in methods:
    for path in sorted((ev / 'scores' / method).glob('*/report.json')):
        d = json.loads(path.read_text())
        name = d.get('corpus_name', path.parent.name)
        if '-cf-' in name:
            continue
        synthesis = next((s for s in d.get('synthesis', []) if s.get('system') == 'evidence-engine'), None)
        # Engine-only score reports may omit the system field.
        if synthesis is None:
            synthesis = next((s for s in d.get('synthesis', []) if 'studies' in s), {})
        reports.append({'corpus': name, 'method': method, 'rows': [r for r in d.get('extraction', {}).get('rows', []) if r.get('level') == 'all'], 'missed': d.get('extraction', {}).get('missed', []), 'unmatched': d.get('extraction', {}).get('unmatched_items', []), 'studies': synthesis.get('studies', []), 'source': path.relative_to(root).as_posix()})
corpora = {}
for path in sorted((ev / 'corpora').glob('*/manifest.json')):
    if '-cf-' in path.parent.name:
        continue
    d = json.loads(path.read_text())
    corpora[path.parent.name] = len(d.get('papers', []))
for r in reports:
    corpora.setdefault(r['corpus'], None)
data = {'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'methods': methods, 'corpora': corpora, 'reports': reports}
template = Path(__file__).with_name('template.html').read_text()
output = root / 'evaluation_dashboard.html'
output.write_text(template.replace('__DATA__', json.dumps(data).replace('<', '\\u003c')))
print(f'Built {output.name}: {len(reports)} reports, {len(corpora)} corpora')
