from __future__ import annotations
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=[json.loads(line) for line in (root/'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
rows=[]
for i in range(20):
    task=base[i]
    long_output=('Previous command: grep -Rni "retrieval" /corpus/*.md\n'
      'Previous output (6 KB):\n'+('file%03d: retrieval evidence and surrounding paper text\n'%(i))*120)
    rows.append({'id':f'long-{i+1:02d}','kind':'long-tool-output','prompt':f"Research concept: {task['prompt'].splitlines()[0].removeprefix('Research concept: ')}\nPrevious steps:\n{long_output}\nWhat is your next command?"})
for i in range(20):
    task=base[(i+20)%len(base)]
    rows.append({'id':f'multi-{i+1:02d}','kind':'multi-step-invitation','prompt':f"Research concept: {task['prompt'].splitlines()[0].removeprefix('Research concept: ')}\nFirst list every relevant paper, then for each paper inspect its methods and results, then compare all findings. What is your next command?"})
out=Path(__file__).with_name('tasks.jsonl')
out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
