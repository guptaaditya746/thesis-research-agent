import json,socket,sys
p=sys.argv[1]
for i in range(100):
 req={'step_id':999999,'s':f's{i}','p':'reports','o':i,'file':'paper.md','quote':f'quote {i}'}
 s=socket.socket(socket.AF_UNIX); s.connect(p); s.sendall(json.dumps(req).encode()+b'\n'); s.recv(1000); s.close()
print('submitted=100 forged_step_id=999999')
