#!/bin/bash
# Run app folders one after another in ONE Claude in Chrome tab (marker cx=<name>), --submit (gates still apply per job).
# Stops at the first handoff so Claude can fix that field in the same tab. Usage: bash run_attached.sh cx=b2 <folder> [<folder> ...]
cd "$(dirname "$0")"; PY="$HOME/.job-agent-venv/bin/python"; M="$1"; shift
for f in "$@"; do
  echo "=================== $f  $(date +%H:%M:%S)"
  out=$("$PY" -u run.py "$f" --attach "$M" --submit 2>&1); echo "$out" | grep -E "STATUS|NOT submitted|CONFIRMED|CAPTCHA|ladder|L2|HANDOFF|verify pass|skipped|TIME|DeepSeek usage"
  echo "$out" | grep -q "STATUS handoff" && { echo "STOP: handoff in $f"; break; }
done
"$PY" close_done_tabs.py | head -2   # Joey 2026-10-28: close finished application tabs
echo "ALL DONE $(date +%H:%M:%S)"
