import asyncio,json,os,time
from openai import AsyncOpenAI
c=AsyncOpenAI(base_url='http://127.0.0.1:4000/v1',api_key=os.environ['LITELLM_MASTER_KEY'],timeout=150)
async def request(label,tokens):
 t=time.monotonic()
 try:
  r=await c.chat.completions.create(model='sub-model',messages=[{'role':'user','content':f'Write a long technical tutorial about reproducible scientific experiments, section {label}. Continue in detail until the output limit.'}],max_tokens=tokens,temperature=.7)
  return {'label':label,'elapsed_s':round(time.monotonic()-t,2),'finish_reason':r.choices[0].finish_reason,'completion_tokens':r.usage.completion_tokens}
 except Exception as e:return {'label':label,'elapsed_s':round(time.monotonic()-t,2),'error':type(e).__name__+': '+str(e)[:220]}
async def main():
 busy=[asyncio.create_task(request(f'busy-{i}',8192)) for i in range(6)]
 await asyncio.sleep(2)
 queued=await request('queued-probe',32)
 done=await asyncio.gather(*busy)
 result={'busy':done,'queued':queued,'note':'Six busy requests saturate two SUB replicas at max_num_seqs=3; the 7th request was submitted 2 s later.'}
 open('tests/L6/queue-timeout-results.json','w').write(json.dumps(result,indent=2));print(json.dumps(result,indent=2));await c.close()
asyncio.run(main())
