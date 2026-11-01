#!/usr/bin/env bash
# UI case study for the meeting: a local $EV with the EV1 LLM-written corpus (rag-llm-s1-mixed), an offline
# engine run on it (regex extractors, no model), the oracle, and the EV1 live scores and comparisons from
# tests/EV1/live-rerun/scores. No GPU, no tunnel. Then serves the web app on http://127.0.0.1:$PORT.
#
#   bash docs/presentation/ui-case.sh            # build (about a minute) and serve
#   bash docs/presentation/ui-case.sh --serve    # serve an existing build
#
# Env: PORT (default 8080), PY (python with the project installed; default: the repo's .venv), EV (default ~/demo-ev-case).
# When EV2 results are in tests/EV2/, the same script shows them too (copied like the EV1 ones).
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
cd "$REPO"
PY=${PY:-$REPO/.venv/Scripts/python.exe}
[ -x "$PY" ] || PY=$REPO/.venv/bin/python
[ -x "$PY" ] || PY=$HOME/Documents/repo/thesis-research-agent/.venv/Scripts/python.exe
export PYTHONPATH=$REPO PYDANTIC_AI_NO_BANNER=1
export EV=${EV:-$HOME/demo-ev-case}
C=rag-llm-s1-mixed
P=domains/rag/protocols/rag-factuality.yaml
ev() { "$PY" -c "import sys; from evaluation.cli import main; sys.exit(main(sys.argv[1:]))" "$@"; }

if [ "${1:-}" != "--serve" ]; then
  rm -rf "$EV"; mkdir -p "$EV/corpora" "$EV/runs" "$EV/scores"
  cp -r "tests/EV1/live-rerun/corpora/$C" "$EV/corpora/$C"
  # papers are hashed in manifest.json with LF endings; a Windows checkout may have CRLF
  for f in "$EV/corpora/$C"/papers/*.md; do sed -i 's/\r$//' "$f"; done
  "$PY" -m evidence.cli run --protocol "$P" --corpus "$EV/corpora/$C" --out "$EV/runs/regex-only" --run-id "$C" --cache "$EV/cache/engine" --extractors regex-only
  ev oracle --protocol "$P" --corpus "$EV/corpora/$C" --out "$EV/runs/oracle/$C"
  ev score --run "$EV/runs/regex-only/$C" --corpus "$EV/corpora/$C" \
    --oracle "$EV/runs/oracle/$C/answer.json" --out "$EV/scores/offline-regex/$C"
  for run in tests/EV1/live-rerun/scores/*/; do
    g=$(basename "$run"); cp -r "$run" "$EV/scores/ev1-$g"
  done
  if [ -d tests/EV2 ]; then
    [ -d tests/EV2/scores ] && for run in tests/EV2/scores/*/; do g=$(basename "$run"); cp -r "$run" "$EV/scores/ev2-$g"; done
    [ -d tests/EV2/ui-case ] && cp -r tests/EV2/ui-case/runs/. "$EV/runs/"
    [ -d tests/EV2/ui-case/corpora ] && cp -r tests/EV2/ui-case/corpora/. "$EV/corpora/"
  fi
  echo "built $EV"
fi
PORT=${PORT:-8080}
echo "open http://127.0.0.1:$PORT (the app answers only to 127.0.0.1, localhost or ::1)"
exec "$PY" -c "import sys; from webapp.cli import main; sys.exit(main(sys.argv[1:]))" serve --port "$PORT"
