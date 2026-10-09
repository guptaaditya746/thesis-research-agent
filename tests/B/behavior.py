from __future__ import annotations
import argparse, json, math, re, statistics, time
from pathlib import Path
from openai import OpenAI
from transformers import AutoTokenizer

p=argparse.ArgumentParser()
p.add_argument('test',choices=['B1','B2'])
p.add_argument('--base-url',default='http://127.0.0.1:8001/v1')
p.add_argument('--model',default='orch')
p.add_argument('--model-path',default='Qwen/Qwen3-30B-A3B-Thinking-2507-FP8')
a=p.parse_args()
root=Path(__file__).resolve().parent
system=(root/'system_prompt.txt').read_text(encoding='utf-8')
tasks=[json.loads(line) for line in (root/'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
tok=AutoTokenizer.from_pretrained(a.model_path)
client=OpenAI(base_url=a.base_url,api_key='x',timeout=1800)
tick=chr(96)*3
blocks=re.compile(tick+r'(?:bash|sh)\n(.*?)'+tick,re.DOTALL)

def run_one(task, thinking, max_tokens):
    start=time.perf_counter()
    response=client.chat.completions.create(
        model=a.model,
        messages=[{'role':'system','content':system},{'role':'user','content':task['prompt']}],
        max_tokens=max_tokens,temperature=0.2,
        extra_body={'chat_template_kwargs':{'enable_thinking':thinking}},
    )
    choice=response.choices[0]; msg=choice.message.model_dump()
    # vLLM/OpenAI responses have exposed Qwen's parsed reasoning under either
    # field name across server versions; keep both in the saved artifact.
    reasoning=msg.get('reasoning_content') or msg.get('reasoning') or ''
    content=msg.get('content') or ''
    rb=blocks.findall(reasoning); cb=blocks.findall(content)
    usage=response.usage.model_dump() if response.usage else {}
    return {
        'id':task['id'],'thinking':thinking,'max_tokens':max_tokens,
        'reasoning_content':reasoning,'content':content,
        'reasoning_tokens':len(tok.encode(reasoning,add_special_tokens=False)),
        'content_tokens':len(tok.encode(content,add_special_tokens=False)),
        'reasoning_nonempty':bool(reasoning.strip()),'block_count':len(cb),
        'reasoning_block_missing_from_content':any(b not in cb for b in rb),
        'finish_reason':choice.finish_reason,'usage':usage,
        'seconds':time.perf_counter()-start,
    }

def summarize(rows):
    rts=[x['reasoning_tokens'] for x in rows]; cts=[x['content_tokens'] for x in rows]
    p95=lambda xs: sorted(xs)[max(0,math.ceil(.95*len(xs))-1)]
    return {
        'n':len(rows),
        'one_block_pct':100*sum(x['block_count']==1 for x in rows)/len(rows),
        'reasoning_nonempty_pct':100*sum(x['reasoning_nonempty'] for x in rows)/len(rows),
        'reasoning_block_missing_count':sum(x['reasoning_block_missing_from_content'] for x in rows),
        'length_cut_count':sum(x['finish_reason']=='length' for x in rows),
        'mean_reasoning_tokens':statistics.mean(rts),'p95_reasoning_tokens':p95(rts),
        'mean_content_tokens':statistics.mean(cts),
        'mean_seconds':statistics.mean(x['seconds'] for x in rows),
    }

out=root/a.test; out.mkdir(parents=True,exist_ok=True)
configs=[(mode,8192) for mode in (True,False)] if a.test=='B1' else [(True,n) for n in (1024,2048,4096,8192,16384)]
for thinking, limit in configs:
    rows=[]
    for task in tasks:
        row=run_one(task,thinking,limit); rows.append(row)
        print(json.dumps({'id':task['id'],'thinking':thinking,'max_tokens':limit,'block_count':row['block_count'],'finish_reason':row['finish_reason'],'reasoning_tokens':row['reasoning_tokens'],'content_tokens':row['content_tokens']},ensure_ascii=False),flush=True)
    name=f"{'thinking' if thinking else 'no-thinking'}-{limit}.jsonl"
    (out/name).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
    summary=summarize(rows)
    (out/(name+'.summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'file':name,'summary':summary},ensure_ascii=False),flush=True)
