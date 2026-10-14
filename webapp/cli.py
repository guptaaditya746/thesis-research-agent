"""`webapp` command line: `webapp serve` (uvicorn) and `webapp openapi` (the API schema as JSON).

`serve` binds to 127.0.0.1 by default: the app has no authentication and is reached through an
SSH tunnel (webapp/README.md). `openapi` prints the schema the frontend's types are generated from
(`webapp openapi > webapp/web/openapi.json`).
"""
from __future__ import annotations

import argparse
import json
import sys


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .settings import REPO

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"webapp: warning: binding to {args.host}; the app has no authentication", file=sys.stderr)
    uvicorn.run("webapp.app:create_app", factory=True, host=args.host, port=args.port, reload=args.reload,
                reload_dirs=[str(REPO / "webapp")] if args.reload else None, log_level=args.log_level)
    return 0


def cmd_openapi(args: argparse.Namespace) -> int:
    from .app import create_app

    schema = create_app().openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webapp")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the backend (and the built frontend) with uvicorn")
    serve.add_argument("--host", default="127.0.0.1", help="interface to bind (default 127.0.0.1: tunnel to it)")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    serve.add_argument("--log-level", default="info")
    serve.set_defaults(func=cmd_serve)
    openapi = sub.add_parser("openapi", help="print the OpenAPI schema (JSON) the frontend types are made from")
    openapi.add_argument("-o", "--output", help="write to this file instead of standard output")
    openapi.set_defaults(func=cmd_openapi)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
