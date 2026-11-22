#!/usr/bin/env python3
"""Consume newline-delimited claim requests from an inherited socket descriptor."""

import argparse
import hashlib
import json
import os
import socket


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--step-id", type=int, required=True)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
    prev = "0" * 64
    count = 0
    channel = socket.socket(fileno=args.fd)
    with open(args.log, "w", encoding="utf-8") as log, channel.makefile("rwb") as stream:
        for line in stream:
            request = json.loads(line)
            event = {key: request[key] for key in ("s", "p", "o", "file", "quote")}
            event["step_id"] = args.step_id
            event["prev_hash"] = prev
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
            event["hash"] = hashlib.sha256(canonical).hexdigest()
            prev = event["hash"]
            log.write(json.dumps(event, sort_keys=True) + "\n")
            log.flush()
            os.fsync(log.fileno())
            stream.write(b'{"ok":true}\n')
            stream.flush()
            count += 1
    print(json.dumps({"count": count, "head": prev}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
