from __future__ import annotations

import os

# Starlette's TestClient sends Host: testserver from the client address "testclient"; the app answers loopback
# names only and takes writes from loopback clients only (webapp/guard.py), so the tests add both.
os.environ.setdefault("WEBAPP_ALLOWED_HOSTS", "127.0.0.1,localhost,::1,testserver")
os.environ.setdefault("WEBAPP_WRITE_CLIENTS", "127.0.0.1,::1,testclient")
