#!/bin/bash
# Run every folder of a prepared batch with --submit (gates still apply per job). Usage: bash run_batch.sh ../../../data/runner/batches/<date>.status.json
cd "$(dirname "$0")"; PY="$HOME/.job-agent-venv/bin/python"
bash ./start_chrome.sh >/dev/null
for f in $("$PY" -c "import json,sys;[print(r['folder']) for r in json.load(open(sys.argv[1])) if r.get('folder')]" "$1"); do
  echo "=================== $f"
  "$PY" run.py "${JSA_HOME:-../../..}/applications/$f" --submit 2>&1 | grep -E "STATUS|NOT submitted|CONFIRMED|CAPTCHA|problems|verify pass|code|no confirmation"
done
echo; echo "== queue (needs you):"; tail -n 20 ../../../data/runner/queue.md 2>/dev/null
echo; echo "== human checks waiting for Joey (JSA-106):"; "$PY" human_check.py --list --push
