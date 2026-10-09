from __future__ import annotations
import json, sys, time
from pathlib import Path

repo=Path(__file__).resolve().parents[2]
corpus_src=repo/'final-final-frontend/UI/files/harness/packages/corpus/src'
sys.path.insert(0,str(corpus_src))
from harness_corpus.tei import parse_tei

ids=json.loads((repo/'tests/D1/selection.json').read_text())
data=repo/'final-final-frontend/UI/files/harness/corpus_data'
tei_dir=data/'.cache/tei'
out=repo/'tests/D1/grobid'
out.mkdir(parents=True,exist_ok=True)
times=[]
for pid in ids:
    anthology=pid.replace('-', '.', 1)
    # IDs use 2025-acl-long-N, whose anthology ID is 2025.acl-long.N.
    venue, number=pid[5:].rsplit('-',1)
    anthology=f'2025.{venue}.{number}'
    path=tei_dir/f'{anthology}.grobid.tei.xml'
    start=time.perf_counter()
    try:
        paper, passages, refs=parse_tei(path.read_bytes(),pid)
        lines=[f"# {paper['title']}",'','Authors: '+', '.join(paper['authors']),'']
        section=None
        for row in passages:
            if row['section_path'] != section:
                section=row['section_path']; lines += [f"## {section}",'']
            lines += [row['text'],'']
        if refs:
            lines += ['## References','']
            lines += [r.get('raw','') for r in refs]
        markdown='\n'.join(lines).strip()+'\n'
        (out/f'{pid}.md').write_text(markdown,encoding='utf-8')
        item={'paper_id':pid,'seconds':time.perf_counter()-start,'chars':len(markdown),'title':paper['title'],'authors':paper['authors'],'sections':len({x['section_path'] for x in passages}),'references':len(refs),'error':None}
    except Exception as exc:
        item={'paper_id':pid,'seconds':time.perf_counter()-start,'chars':0,'title':'','authors':[],'sections':0,'references':0,'error':f'{type(exc).__name__}: {exc}'}
    times.append(item); print(json.dumps(item,ensure_ascii=False),flush=True)
(repo/'tests/D1/grobid_times.json').write_text(json.dumps(times,indent=2,ensure_ascii=False)+'\n')
