from __future__ import annotations
import json,re,time,statistics
from pathlib import Path
from openai import OpenAI
from transformers import AutoTokenizer
here=Path(__file__).resolve().parent
system=(here.parent/'system_prompt.txt').read_text(encoding='utf-8')
tasks=[json.loads(s) for s in (here/'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
model_path='Qwen/Qwen3.8-27B-FP8';tok=AutoTokenizer.from_pretrained(model_path)
c=OpenAI(base_url='http://127.0.0.1:8001/v1',api_key='x',timeout=1800)
blocks=re.compile(r'```(?:bash|sh)\n(.*?)```',re.DOTALL);rows=[]
for task in tasks:
 t=time.perf_counter();r=c.chat.completions.create(model='orch',messages=[{'role':'system','content':system},{'role':'user','content':task['prompt']}],max_tokens=8192,temperature=0.2,extra_body={'chat_template_kwargs':{'enable_thinking':False}})
 ch=r.choices[0];m=ch.message.model_dump();content=m.get('content') or '';reasoning=m.get('reasoning_content') or m.get('reasoning') or ''
 row={'id':task['id'],'kind':task['kind'],'prompt':task['prompt'],'content':content,'reasoning':reasoning,'block_count':len(blocks.findall(content)),'reasoning_block_missing_from_content':any(b not in blocks.findall(content) for b in blocks.findall(reasoning)),'reasoning_tokens':len(tok.encode(reasoning,add_special_tokens=False)),'content_tokens':len(tok.encode(content,add_special_tokens=False)),'finish_reason':ch.finish_reason,'usage':r.usage.model_dump() if r.usage else None,'seconds':time.perf_counter()-t}
 rows.append(row);print(json.dumps({'id':row['id'],'block_count':row['block_count'],'finish_reason':row['finish_reason']},ensure_ascii=False),flush=True)
with (here/'results.jsonl').open('w',encoding='utf-8') as f:
 for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
for kind in ('long-tool-output','multi-step-invitation'):
 group=[r for r in rows if r['kind']==kind]
 print(json.dumps({'kind':kind,'n':len(group),'one_block_pct':100*sum(r['block_count']==1 for r in group)/len(group),'two_or_more_blocks':sum(r['block_count']>1 for r in group),'prose_only':sum(r['block_count']==0 for r in group),'mean_seconds':statistics.mean(r['seconds'] for r in group)}),flush=True)
