from __future__ import annotations
import argparse,json,re,time
from pathlib import Path
from openai import OpenAI
p=argparse.ArgumentParser();p.add_argument('--model',default='orch');p.add_argument('--base-url',default='http://127.0.0.1:8001/v1');p.add_argument('--model-path',default='Qwen/Qwen3.8-27B-FP8');p.add_argument('--thinking',action='store_true');p.add_argument('--out',default='tests/B/B4/loop.jsonl');a=p.parse_args()
root=Path(__file__).resolve().parents[3]; system=(root/'tests/B/system_prompt.txt').read_text(encoding='utf-8')
tick='`'*3; block=re.compile(tick+r'(?:bash|sh)\n(.*?)'+tick,re.S)
client=OpenAI(base_url=a.base_url,api_key='x',timeout=1800)
out=root/a.out;out.parent.mkdir(parents=True,exist_ok=True)
out.write_text('',encoding='utf-8')
tool_call=re.compile(r'<function=bash>\s*(.*?)(?:</parameter>|</function>|</tool_call>|$)',re.S)
messages=[{'role':'system','content':system},{'role':'user','content':'Research concept: papers evaluated on a dataset named XYZZY, which may not occur in this corpus. Start searching and report only evidence from /corpus.'}]
rows=[]
for turn in range(1,11):
 t=time.perf_counter();r=client.chat.completions.create(model=a.model,messages=messages,max_tokens=4096,temperature=0.2,extra_body={'chat_template_kwargs':{'enable_thinking':a.thinking}})
 ch=r.choices[0];m=ch.message.model_dump();content=m.get('content') or '';reasoning=m.get('reasoning_content') or m.get('reasoning') or '';found=block.findall(content)
 call=tool_call.search(content)
 payload=call.group(1) if call else content
 payload=re.sub(r'^<parameter=command>\s*','',payload)
 command=(found[0] if found else payload).strip();normalized=' '.join(command.split())
 row={'turn':turn,'command':command,'normalized_command':normalized,'block_count':len(found),'reasoning':reasoning,'content':content,'finish_reason':ch.finish_reason,'seconds':time.perf_counter()-t,'usage':r.usage.model_dump() if r.usage else None}
 rows.append(row)
 with out.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(json.dumps({'turn':turn,'command':normalized[:180],'block_count':len(found),'finish_reason':ch.finish_reason}),flush=True)
 messages.append({'role':'assistant','content':content})
 messages.append({'role':'user','content':'Tool output for the command above:\n(no matches)\nWhat is your next command?'})
seen={};repeat_turn=None
for x in rows:
 k=x['normalized_command']
 if k in seen and repeat_turn is None:repeat_turn=x['turn']
 seen[k]=x['turn']
print(json.dumps({'model':a.model,'thinking':a.thinking,'first_repeated_command_turn':repeat_turn,'unique_commands_by_turn_4':len({x['normalized_command'] for x in rows[:4]}),'strategy_changed_by_turn_4':len({x['normalized_command'] for x in rows[:4]})>1,'commands':[x['normalized_command'] for x in rows]},ensure_ascii=False),flush=True)
