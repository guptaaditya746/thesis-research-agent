import json,os,time
from openai import OpenAI
from transformers import AutoTokenizer
tok=AutoTokenizer.from_pretrained('/mnt/ceph/storage/data-tmp/current/xepi3167/.cache/huggingface/hub/models--Qwen--Qwen3.8-27B-FP8/snapshots/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a',local_files_only=True)
base=tok.encode('Research evidence and results are reported in this paper. ',add_special_tokens=False)
ids=(base*((60000//len(base))+1))[:60000]
prompt=tok.decode(ids,skip_special_tokens=True)+'\nContinue an extended technical synthesis until the output token limit.'
c=OpenAI(base_url='http://127.0.0.1:4000/v1',api_key=os.environ['LITELLM_MASTER_KEY'],timeout=150,max_retries=0)
t=time.monotonic(); result={'input_token_target':60000}
try:
 r=c.chat.completions.create(model='orch-model',messages=[{'role':'user','content':prompt}],max_tokens=4096,temperature=.2,extra_body={'ignore_eos':True})
 result.update(elapsed_s=round(time.monotonic()-t,2),prompt_tokens=r.usage.prompt_tokens,completion_tokens=r.usage.completion_tokens,finish_reason=r.choices[0].finish_reason)
except Exception as e: result.update(elapsed_s=round(time.monotonic()-t,2),error=type(e).__name__+': '+str(e)[:400])
open('tests/L6/forced-timeout-results.json','w').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
c.close()
