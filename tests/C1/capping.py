from __future__ import annotations
import hashlib,json,os,signal,subprocess,tempfile,time,shutil
from pathlib import Path
from transformers import AutoTokenizer
ROOT=Path(__file__).resolve().parents[2]
RUN=Path(__file__).resolve().parent/'run'
WORK=RUN/'work'; OUT=WORK/'out'; OUT.mkdir(parents=True,exist_ok=True)
EVENTS=RUN/'events.jsonl'; EVENTS.parent.mkdir(parents=True,exist_ok=True)
CAP=8192
PAPER=max((ROOT/'final-final-frontend/UI/files/harness/corpus_data/outlines').glob('*.md'),key=lambda p:p.stat().st_size)
commands=[
  (f"cat {PAPER}",'longest-paper'),
  ("python3 -c \"print('x'*100000)\"",'large-stdout'),
  ("python3 -c \"import sys;sys.stderr.write('e'*100000)\"",'large-stderr'),
  ("yes | head -c 50000000",'50mb-output'),
]
tok=AutoTokenizer.from_pretrained('Qwen/Qwen3.8-27B-FP8');prev='0'*64;rows=[]
for step,(command,label) in enumerate(commands,1):
  start=time.perf_counter()
  with tempfile.TemporaryFile() as stdout_tmp,tempfile.TemporaryFile() as stderr_tmp:
    proc=subprocess.Popen(['bash','-lc',command],stdout=stdout_tmp,stderr=stderr_tmp,start_new_session=True)
    try: rc=proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
      os.killpg(proc.pid,signal.SIGKILL);rc=proc.wait()
    stdout_tmp.seek(0);stdout_data=stdout_tmp.read();stderr_tmp.seek(0);stderr_data=stderr_tmp.read()
  stdout_path=OUT/f'{step}.txt';stdout_path.write_bytes(stdout_data)
  stderr_path=None
  if len(stderr_data)>CAP:
    stderr_path=OUT/f'{step}.stderr.txt';stderr_path.write_bytes(stderr_data)
  head=stdout_data[:CAP].decode('utf-8',errors='replace')
  observation=head
  if len(stdout_data)>CAP: observation+=f'\n[output capped; full stdout at /work/out/{step}.txt]'
  stderr_observation=stderr_data[:CAP].decode('utf-8',errors='replace')
  if len(stderr_data)>CAP: stderr_observation+=f'\n[stderr capped; full stderr at /work/out/{step}.stderr.txt]'
  before=tok.encode('Research agent context before tool output.\n',add_special_tokens=False)
  after=tok.encode('Research agent context before tool output.\n'+observation+'\n'+stderr_observation,add_special_tokens=False)
  row={'step':step,'label':label,'command':command,'exit_code':rc,'stdout_bytes':len(stdout_data),'stderr_bytes':len(stderr_data),'stdout_path':str(stdout_path.relative_to(RUN)),'stdout_head':head,'stderr_path':None if stderr_path is None else str(stderr_path.relative_to(RUN)),'observation':observation,'context_tokens_before':len(before),'context_tokens_after':len(after),'seconds':time.perf_counter()-start,'prev_hash':prev}
  payload=json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
  digest=hashlib.sha256(payload).hexdigest();row['hash']=digest;prev=digest;rows.append(row)
  with EVENTS.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  print(json.dumps({'step':step,'label':label,'stdout_bytes':len(stdout_data),'stderr_bytes':len(stderr_data),'observation_bytes':len(observation.encode()),'context_tokens_before':len(before),'context_tokens_after':len(after),'exit_code':rc},ensure_ascii=False),flush=True)
print(json.dumps({'run_dir':str(RUN),'longest_paper':str(PAPER),'steps':len(rows),'largest_stdout':max(r['stdout_bytes'] for r in rows),'largest_context_observation_bytes':max(len(r['observation'].encode()) for r in rows),'events':str(EVENTS)},ensure_ascii=False))
