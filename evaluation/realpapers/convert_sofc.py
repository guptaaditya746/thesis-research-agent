"""Convert the original SOFC-Exp corpus to the runbook's SOFC JSON layout.

The corpus does not annotate a value-to-material relation. Preserve that uncertainty:
values have material=None, so the existing ranking gate refuses unsupported rankings.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

_NUMBER = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)\s+([^\d]+?)\s*$")


def convert(archive: Path) -> dict:
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        frames = sorted(n for n in names if '/sofc-exp-corpus/annotations/frames/' in n and n.endswith('.csv'))
        if not frames:
            raise ValueError('SOFC-Exp archive contains no frame files')
        papers = []
        for filename in frames:
            base = filename.split('/annotations/frames/')[0]
            paper_id = Path(filename).stem
            text = z.read(f'{base}/texts/{paper_id}.txt').decode('utf-8')
            sentence_rows = z.read(f'{base}/annotations/sentences/{paper_id}.csv').decode('utf-8').splitlines()
            sentences = {}
            for row in sentence_rows:
                columns = row.split('\t')
                sentences[int(columns[0])] = text[int(columns[2]):int(columns[3])]
            spans, experiments, links = {}, [], []
            current = None
            for row in z.read(filename).decode('utf-8').splitlines():
                parts = row.split('\t')
                if parts[0] == 'SPAN':
                    _, sid, label, sentence, start, end, *_ = parts
                    sentence_no, start, end = int(sentence), int(start), int(end)
                    raw = sentences[sentence_no][start:end]
                    spans[sid] = {'id': sid, 'type': label, 'sentence_id': sentence_no,
                                  'start': start, 'end': end, 'text': raw}
                elif parts[0] == 'EXPERIMENT':
                    current = {'id': parts[1], 'trigger_span_id': parts[2], 'slot_refs': []}
                    experiments.append(current)
                elif parts[0] == 'LINK':
                    links.append({'type': parts[1], 'source': parts[2], 'target': parts[3]})
                elif parts[0] == '' and len(parts) >= 3 and current is not None:
                    current['slot_refs'].append({'slot': parts[1], 'span_id': parts[2]})
                elif row.strip():
                    raise ValueError(f'{filename}: unknown record {row!r}')
            measures = defaultdict(set)
            for experiment in experiments:
                slots = defaultdict(list)
                for ref in experiment['slot_refs']:
                    span = spans[ref['span_id']]
                    slots[ref['slot']].append(span['text'])
                    if span['type'] == 'VALUE':
                        measures[ref['span_id']].add(ref['slot'])
                # Preserve repeated slot values in one string for the existing scorer;
                # the exact repeated references remain available in slot_refs.
                experiment['slots'] = {key: '; '.join(values) for key, values in slots.items()}
            values = []
            for span in spans.values():
                if span['type'] != 'VALUE':
                    continue
                match = _NUMBER.fullmatch(span['text'])
                labels = sorted(measures[span['id']])
                values.append({'value': float(match.group(1)) if match else None,
                               'unit': match.group(2) if match else None,
                               'material': None, 'measure': labels[0] if len(labels) == 1 else None,
                               'raw': span['text'], 'span_id': span['id'], 'measure_candidates': labels})
            papers.append({'id': paper_id, 'text': text, 'values': values, 'experiments': experiments,
                           'spans': list(spans.values()), 'links': links})
    return {'papers': papers, 'source_format': 'SOFC-Exp frame annotations',
            'limitations': ['Material-to-value links are not explicitly annotated; ranking is disabled.',
                            'Complex numeric expressions are preserved as raw text.']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = convert(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(f'refusing to overwrite {args.output}')
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
