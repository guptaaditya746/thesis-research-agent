from __future__ import annotations
import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parent/'run/events.jsonl';prev='0'*64;n=0
for line in p.read_text(encoding='utf-8').splitlines():
 row=json.loads(line);assert row['prev_hash']==prev
 digest=row.pop('hash');actual=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();assert actual==digest
 row['hash']=digest;prev=digest;n+=1
print(f'PASS: verified {n} event hashes')
