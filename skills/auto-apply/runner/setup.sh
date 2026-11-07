#!/bin/bash
# One-time runner setup on the user's Mac (run in Terminal):  bash <repo>/skills/auto-apply/runner/setup.sh
# Creates a private Python environment ~/.job-agent-venv (does not touch the system / Homebrew Python).
cd "$(dirname "$0")"
VENV="$HOME/.job-agent-venv"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 /usr/bin/python3 python3; do
  p=$(command -v $c 2>/dev/null) || continue
  v=$($p -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null) || continue
  case $v in 3.9|3.10|3.11|3.12|3.13) PY=$p; break;; esac
done
[ -z "$PY" ] && PY=$(command -v python3)
echo "== using $PY ($($PY --version 2>&1))"
if [ ! -x "$VENV/bin/python" ]; then $PY -m venv "$VENV" || { echo "venv failed"; exit 1; }; fi
"$VENV/bin/python" -m pip install --upgrade pip playwright >/tmp/job-agent-pip.log 2>&1 \
  && echo "== playwright installed in $VENV" \
  || { echo "pip failed — last lines:"; tail -15 /tmp/job-agent-pip.log; exit 1; }
command -v node >/dev/null && echo "== node: $(node -v)" || echo "== node: not installed (fine — rules run inside Chrome)"
GMAIL=$(python3 -c "import sys; sys.path.insert(0, '../../../config'); import jsa_profile; print(jsa_profile.get('accounts.gmail') or '')")
security find-generic-password -a "$GMAIL" -s job-agent-gmail >/dev/null 2>&1 && echo "== Gmail app password: in Keychain" || echo "== Gmail app password: NOT yet in Keychain (step 2 of SETUP.md)"
bash ./start_chrome.sh
"$VENV/bin/python" - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br = pw.chromium.connect_over_cdp('http://127.0.0.1:9222'); p = br.contexts[0].new_page()
    p.goto('https://boards-api.greenhouse.io/v1/boards/businessolver/jobs/8281727?questions=true')
    print('== Greenhouse API reachable:', '"questions"' in p.content()); p.close()
PY
echo "== setup check done. Run the agent with: $VENV/bin/python"
