from __future__ import annotations
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
first={}
for line in (root/'tests/D2/first_pass.sha256').read_text().splitlines():
 h,name=line.split(maxsplit=1);first[Path(name).name]=h
rows=[]
for path in sorted((root/'tests/D2/docling_repeat').glob('*.md')):
 current=hashlib.sha256(path.read_bytes()).hexdigest(); prior=first.get(path.name)
 rows.append({'file':path.name,'first_sha256':prior,'second_sha256':current,'identical':prior==current})
(root/'tests/D2/hash_comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
(root/'tests/D2/hash_comparison.md').write_text('# D2 Docling determinism\n\n| File | Identical SHA-256 | Hash |\n|---|---:|---|\n'+''.join(f"| {r['file']} | {r['identical']} | `{r['second_sha256']}` |\n" for r in rows))
print(json.dumps({'n':len(rows),'identical':sum(r['identical'] for r in rows),'different':[r['file'] for r in rows if not r['identical']]},indent=2))
