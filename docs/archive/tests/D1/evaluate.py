from __future__ import annotations
import json, re
from pathlib import Path

repo=Path(__file__).resolve().parents[2]
ids=json.loads((repo/'tests/D1/selection.json').read_text())
data=repo/'final-final-frontend/UI/files/harness/corpus_data'
papers={json.loads(line)['paper_id']:json.loads(line) for line in (data/'papers.jsonl').read_text().splitlines()}
refs={}
for line in (data/'references.jsonl').open():
    row=json.loads(line)
    refs.setdefault(row['paper_id'],[]).append(row)
rows=[]
for pid in ids:
    expected=papers[pid]
    for converter in ('grobid','docling','marker'):
        path=repo/f'tests/D1/{converter}/{pid}.md'
        raw=path.read_text(encoding='utf-8') if path.exists() else ''
        title=expected['title']
        title_present=bool(raw and title.casefold() in raw.casefold())
        authors=expected['authors']
        positions=[raw.casefold().find(x.casefold()) for x in authors] if raw else []
        author_order=bool(positions and all(pos>=0 for pos in positions) and positions==sorted(positions))
        headings=re.findall(r'(?m)^#{1,6}\s+\S',raw)
        heading=re.search(r'(?im)^#{0,6}\s*(?:references|bibliography)\s*$',raw)
        if converter=='grobid':
            ref_rows=len(refs.get(pid,[]))
        elif heading:
            # Docling commonly emits bibliography entries as unnumbered,
            # blank-line-separated author/year paragraphs.
            tail=raw[heading.end():]
            ref_rows=sum(bool(re.search(r'\b(?:19|20)\d{2}\b',part)) for part in re.split(r'\n\s*\n',tail))
        else:
            ref_rows=0
        has_refs=ref_rows>0 and heading is not None
        table_rows=sum(bool(re.match(r'^\s*\|.*\|\s*$',line)) for line in raw.splitlines())
        rows.append({
            'paper_id':pid,'converter':converter,'title_matches_DBLP':title_present,
            'author_order_matches_DBLP':author_order,'section_headings':len(headings),
            'references_detected':ref_rows if has_refs else 0,'table_rows':table_rows,
            'interleaved_columns':'manual review required' if raw else 'not converted',
            'chars':len(raw),
        })
(repo/'tests/D1/criteria.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
with (repo/'tests/D1/criteria.md').open('w') as f:
    f.write('# D1 conversion criteria\n\n')
    f.write('Title/authors are compared to DBLP-sourced corpus metadata. GROBID rows use cached GROBID TEI; Docling rows use direct PDF-to-Markdown output. Marker is unavailable. The column-flow visual check remains open.\n\n')
    f.write('| Paper | Converter | Title | Author order | Sections | References | Table rows | Columns | chars |\n')
    f.write('|---|---|---:|---:|---:|---:|---:|---|---:|\n')
    for x in rows:
        f.write(f"| {x['paper_id']} | {x['converter']} | {x['title_matches_DBLP']} | {x['author_order_matches_DBLP']} | {x['section_headings']} | {x['references_detected']} | {x['table_rows']} | {x['interleaved_columns']} | {x['chars']} |\n")
print(repo/'tests/D1/criteria.md')
