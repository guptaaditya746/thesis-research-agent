import asyncio,json,os,time
from openai import AsyncOpenAI
c=AsyncOpenAI(base_url='http://127.0.0.1:4000/v1',api_key=os.environ['LITELLM_MASTER_KEY'],timeout=180)
async def seed():
 t=time.monotonic(); r=await c.chat.completions.create(model='orch-model',messages=[{'role':'user','content':'Return exactly the number 7.'}],max_tokens=32,temperature=0,seed=1,extra_body={'chat_template_kwargs':{'enable_thinking':False}})
 return {'text':r.choices[0].message.content,'finish_reason':r.choices[0].finish_reason,'seconds':round(time.monotonic()-t,3)}
async def sub(n,limit=700):
 t=time.monotonic()
 try:
  r=await c.chat.completions.create(model='sub-model',messages=[{'role':'user','content':f'Write a detailed explanation of retrieval augmented generation, version {n}.'}],max_tokens=limit,temperature=.7)
  return {'seconds':round(time.monotonic()-t,3),'finish_reason':r.choices[0].finish_reason}
 except Exception as e:return {'seconds':round(time.monotonic()-t,3),'error':type(e).__name__+': '+str(e)[:200]}
async def main():
 alone=[await seed() for _ in range(10)]
 busy=[asyncio.create_task(sub(i,900)) for i in range(6)]
 await asyncio.sleep(2)
 t=time.monotonic(); queued=asyncio.create_task(sub('queued',32))
 under=[]
 for _ in range(10):
  try: under.append(await seed())
  except Exception as e: under.append({'error':type(e).__name__+': '+str(e)[:150]})
 q=await queued; done=await asyncio.gather(*busy)
 result={'seed_alone':{'distinct':len(set(x.get('text') for x in alone)),'samples':alone},'seed_under_sub_load':{'distinct':len(set(x.get('text') for x in under)),'samples':under},'queue_probe':{'capacity_assumption':'two SUB replicas × max_num_seqs=3; six busy requests, seventh submitted two seconds later','queued_request':q,'busy_requests':done}}
 open('tests/L6/seed-queue-results.json','w').write(json.dumps(result,indent=2));print(json.dumps(result,indent=2));await c.close()
asyncio.run(main())
