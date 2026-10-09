from __future__ import annotations
import argparse,json,os,re,time,statistics
from pathlib import Path
from openai import OpenAI
from transformers import AutoTokenizer
here=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--base-url',default='http://127.0.0.1:8001/v1')
p.add_argument('--model',default='orch')
p.add_argument('--api-key-env',default='LLM_BACKEND_KEY',help='LITELLM_MASTER_KEY when going through the proxy')
p.add_argument('--out',default=str(here/'results.jsonl'))
a=p.parse_args()
system=(here.parent/'system_prompt.txt').read_text(encoding='utf-8')
tasks=[json.loads(s) for s in (here/'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
model_path='Qwen/Qwen3.8-27B-FP8';tok=AutoTokenizer.from_pretrained(model_path)
c=OpenAI(base_url=a.base_url,api_key=os.getenv(a.api_key_env,'x'),timeout=1800)
blocks=re.compile(r'```(?:bash|sh)\n(.*?)```',re.DOTALL);rows=[]
for task in tasks:
 t=time.perf_counter();r=c.chat.completions.create(model=a.model,messages=[{'role':'system','content':system},{'role':'user','content':task['prompt']}],max_tokens=8192,temperature=0.2,extra_body={'chat_template_kwargs':{'enable_thinking':False}})
 ch=r.choices[0];m=ch.message.model_dump();content=m.get('content') or '';reasoning=m.get('reasoning_content') or m.get('reasoning') or ''
 row={'id':task['id'],'kind':task['kind'],'prompt':task['prompt'],'content':content,'reasoning':reasoning,'block_count':len(blocks.findall(content)),'reasoning_block_missing_from_content':any(b not in blocks.findall(content) for b in blocks.findall(reasoning)),'reasoning_tokens':len(tok.encode(reasoning,add_special_tokens=False)),'content_tokens':len(tok.encode(content,add_special_tokens=False)),'finish_reason':ch.finish_reason,'usage':r.usage.model_dump() if r.usage else None,'seconds':time.perf_counter()-t}
 rows.append(row);print(json.dumps({'id':row['id'],'block_count':row['block_count'],'finish_reason':row['finish_reason']},ensure_ascii=False),flush=True)
out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
with out.open('w',encoding='utf-8') as f:
 for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
for kind in ('long-tool-output','multi-step-invitation'):
 group=[r for r in rows if r['kind']==kind]
 print(json.dumps({'kind':kind,'n':len(group),'one_block_pct':100*sum(r['block_count']==1 for r in group)/len(group),'two_or_more_blocks':sum(r['block_count']>1 for r in group),'prose_only':sum(r['block_count']==0 for r in group),'nonempty_reasoning':sum(bool(r['reasoning']) for r in group),'mean_seconds':statistics.mean(r['seconds'] for r in group)}),flush=True)
