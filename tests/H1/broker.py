import hashlib,json,os,socket,threading
sockpath=os.path.abspath('tests/S5/scratch/claim-broker.sock')
logpath=os.path.abspath('tests/H1/private/claims.jsonl')
os.makedirs(os.path.dirname(logpath),exist_ok=True)
try: os.unlink(sockpath)
except FileNotFoundError: pass
open(logpath,'w').close()
current_step=42
s=socket.socket(socket.AF_UNIX); s.bind(sockpath); s.listen(1)
prev='0'*64; count=0
while count<100:
 conn,_=s.accept()
 with conn:
  data=b''
  while not data.endswith(b'\n'):
   chunk=conn.recv(65536)
   if not chunk: break
   data+=chunk
  req=json.loads(data)
  event={'step_id':current_step,'s':req['s'],'p':req['p'],'o':req['o'],'file':req['file'],'quote':req['quote'],'prev_hash':prev}
  canonical=json.dumps(event,sort_keys=True,separators=(',',':')).encode()
  event['hash']=hashlib.sha256(canonical).hexdigest(); prev=event['hash']
  with open(logpath,'a') as f: f.write(json.dumps(event,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
  conn.sendall(b'{"ok":true}\n'); count+=1
print(json.dumps({'count':count,'head':prev}),flush=True)
s.close()
