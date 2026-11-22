import hashlib,json
from pathlib import Path
p=Path('tests/S2/run/events.jsonl'); prev='0'*64; rows=[]
for line in p.read_text(encoding='utf-8').splitlines():
 row=json.loads(line); assert row['prev_hash']==prev
 digest=row.pop('hash'); actual=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(); assert digest==actual
 row['hash']=digest; prev=digest; rows.append(row)
assert rows[-1]['event']=='run_aborted', rows[-1]
print(f'PASS: verified {len(rows)} events; final={rows[-1]["event"]}')
