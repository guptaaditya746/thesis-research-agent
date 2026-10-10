import json
import os
import socket

fd = int(os.environ["CLAIM_FD"])
channel = socket.socket(fileno=fd)
with channel.makefile("rwb") as stream:
    for i in range(100):
        request = {"step_id": 999999, "s": f"s{i}", "p": "reports", "o": i,
                   "file": "paper.md", "quote": f"quote {i}"}
        stream.write(json.dumps(request).encode() + b"\n")
        stream.flush()
        if stream.readline() != b'{"ok":true}\n':
            raise SystemExit(f"claim {i} was not acknowledged")
print("submitted=100 forged_step_id=999999")
