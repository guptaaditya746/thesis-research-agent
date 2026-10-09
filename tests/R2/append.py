import concurrent.futures, fcntl, json, os, statistics, time, hashlib
from pathlib import Path
NPROC=8; N=10000

def writer(path, lock, worker):
 fd=os.open(path,os.O_CREAT|os.O_WRONLY|os.O_APPEND,0o600); times=[]
 try:
  for i in range(N):
   size=1024+((i*7919+worker*1013)%15360)
   body=hashlib.sha256(f'{worker}:{i}'.encode()).hexdigest()
   # JSON record with variable sized text to produce 1-16 KB lines.
   rec={'worker':worker,'seq':i,'payload':body+'x'*(size-100)}
   line=(json.dumps(rec,separators=(',',':'))+'\n').encode()
   if lock: fcntl.flock(fd,fcntl.LOCK_EX)
   os.write(fd,line)
   t=time.perf_counter_ns(); os.fsync(fd); times.append((time.perf_counter_ns()-t)/1e6)
   if lock: fcntl.flock(fd,fcntl.LOCK_UN)
 finally: os.close(fd)
 return times

def run(label, lock):
 p=Path(f'tests/R2/{label}.jsonl'); p.unlink(missing_ok=True); start=time.time()
 with concurrent.futures.ProcessPoolExecutor(NPROC) as ex: lat=[x for xs in ex.map(writer,[str(p)]*NPROC,[lock]*NPROC,range(NPROC)) for x in xs]
 counts=0; bad=0
 with p.open('rb') as f:
  for line in f:
   try: json.loads(line); counts+=1
   except Exception: bad+=1
 result={'mode':label,'records':counts,'bad':bad,'expected':NPROC*N,'p50_fsync_ms':statistics.median(lat),'p99_fsync_ms':sorted(lat)[int(.99*(len(lat)-1))],'bytes':p.stat().st_size,'elapsed_s':round(time.time()-start,1)}
 with open(f'tests/R2/{label}.result.json','w') as f: json.dump(result,f,indent=2)
 print(result,flush=True)
 p.unlink()
if __name__=='__main__':
 run('append-only',False)
 run('append-flock',True)
