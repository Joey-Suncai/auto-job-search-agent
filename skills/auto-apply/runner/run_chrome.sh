#!/bin/bash
# LaunchAgent entry (com.jobagent.chrome): exec Chrome in the foreground so launchd supervises it (JSA-378).
# A backgrounded child would be killed when this job exits. Hand / batch use: start_chrome.sh (returns once 9222 answers).
PROFILE="$HOME/.job-agent-chrome"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1; then echo "job Chrome already running"; exit 0; fi
# Chrome missing: exit 0 so KeepAlive(SuccessfulExit=false) does not loop on it
[ -x "$CHROME" ] || { echo "Google Chrome not found in /Applications"; exit 0; }
exec "$CHROME" --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check "about:blank" >/dev/null 2>&1
