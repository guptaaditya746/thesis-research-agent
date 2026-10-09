import asyncio, json, os, time
from openai import AsyncOpenAI
from jsonschema import Draft202012Validator

BASE='http://127.0.0.1:4000/v1'
KEY=os.environ['LITELLM_MASTER_KEY']
c=AsyncOpenAI(base_url=BASE, api_key=KEY, timeout=180)
SCHEMA={"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"definition":{"type":"string"},"measure":{"type":"object","properties":{"operation":{"enum":["count","rank","compare"]},"of":{"type":"string"},"group_by":{"type":"string"},"order":{"enum":["asc","desc"]}},"required":["operation","of","group_by","order"],"additionalProperties":False},"scope":{"type":"object","properties":{"papers":{"type":"string"}},"required":["papers"],"additionalProperties":False},"answer_shape":{"type":"object","properties":{"kind":{"enum":["table","graph"]},"columns":{"type":"array","minItems":1,"items":{"type":"object","properties":{"name":{"type":"string"},"type":{"type":"string"}},"required":["name","type"],"additionalProperties":False}}},"required":["kind","columns"],"additionalProperties":False},"competency_questions":{"type":"array","minItems":2,"maxItems":3,"items":{"type":"string"}},"needs":{"type":"array","minItems":1,"items":{"type":"string"}},"subschema":{"type":"object","properties":{"classes":{"type":"array","minItems":1,"items":{"type":"string"}},"relations":{"type":"array","minItems":1,"items":{"type":"string"}}},"required":["classes","relations"],"additionalProperties":False}},"required":["id","title","definition","measure","scope","answer_shape","competency_questions","needs","subschema"],"additionalProperties":False}
async def call(prompt, **kw):
 return await c.chat.completions.create(model='orch-model',messages=[{'role':'user','content':prompt}],max_tokens=kw.pop('max_tokens',1200),temperature=kw.pop('temperature',0),**kw)
async def main():
 out=[]
 # Exact 60k-token input from the same local tokenizer snapshot used by ORCH.
 from transformers import AutoTokenizer
 tok=AutoTokenizer.from_pretrained('/mnt/ceph/storage/data-tmp/current/xepi3167/.cache/huggingface/hub/models--Qwen--Qwen3.8-27B-FP8/snapshots/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a',local_files_only=True)
 base=tok.encode('Research evidence and results are reported in this paper. ',add_special_tokens=False)
 ids=(base*((60000//len(base))+1))[:60000]
 prompt=tok.decode(ids,skip_special_tokens=True)+'\nWrite an extended evidence summary.'
 t=time.monotonic()
 try:
  r=await call(prompt,max_tokens=4096,temperature=.2)
  out.append({'test':'long_prompt','elapsed_s':round(time.monotonic()-t,2),'prompt_tokens':r.usage.prompt_tokens,'completion_tokens':r.usage.completion_tokens,'finish_reason':r.choices[0].finish_reason})
 except Exception as e: out.append({'test':'long_prompt','elapsed_s':round(time.monotonic()-t,2),'error':type(e).__name__+': '+str(e)[:300]})
 # JSON schema: 20 bounded requests, five concurrent per batch.
 async def schema_one(i):
  try:
   r=await call('Create a research brief for counting first authors in ACL 2025. Return a schema-valid JSON object.',max_tokens=512,response_format={'type':'json_schema','json_schema':{'name':'research_brief','strict':True,'schema':SCHEMA}},extra_body={'chat_template_kwargs':{'enable_thinking':False}})
   obj=json.loads(r.choices[0].message.content); Draft202012Validator(SCHEMA).validate(obj); return {'ok':True,'finish':r.choices[0].finish_reason}
  except Exception as e: return {'ok':False,'error':type(e).__name__+': '+str(e)[:150]}
 schema=[]
 for off in range(0,20,5): schema.extend(await asyncio.gather(*(schema_one(i) for i in range(off,off+5))))
 out.append({'test':'schema','valid':sum(x['ok'] for x in schema),'total':20,'errors':[x.get('error') for x in schema if not x['ok']][:5]})
 async def sample(model='orch-model'):
  r=await c.chat.completions.create(model=model,messages=[{'role':'user','content':'Return exactly the number 7.'}],max_tokens=32,temperature=0,seed=1)
  return r.choices[0].message.content
 alone=[]
 for _ in range(10):
  try: alone.append(await sample())
  except Exception as e: alone.append('ERR:'+type(e).__name__)
 out.append({'test':'seed_alone','distinct_outputs':len(set(alone)),'outputs':alone})
 # Drive three sub requests concurrently, then sample ten orch outputs while they run.
 async def subload():
  try: return await c.chat.completions.create(model='sub-model',messages=[{'role':'user','content':'Write a detailed explanation of retrieval augmented generation.'}],max_tokens=1000,temperature=.7)
  except Exception as e: return e
 loads=[asyncio.create_task(subload()) for _ in range(3)]
 await asyncio.sleep(1)
 loaded=[]
 for _ in range(10):
  try: loaded.append(await sample())
  except Exception as e: loaded.append('ERR:'+type(e).__name__)
 await asyncio.gather(*loads)
 out.append({'test':'seed_under_sub_load','distinct_outputs':len(set(loaded)),'outputs':loaded})
 with open('tests/L6/results.json','w') as f: json.dump(out,f,indent=2)
 print(json.dumps(out,indent=2),flush=True)
 await c.close()
asyncio.run(main())
