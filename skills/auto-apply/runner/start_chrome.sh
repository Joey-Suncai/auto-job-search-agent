#!/bin/bash
# Start the dedicated job Chrome (separate profile, remote control only from this Mac: 127.0.0.1:9222).
# First time: sign in to nothing personal; keep this window for applications only.
PROFILE="$HOME/.job-agent-chrome"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1; then echo "job Chrome already running"; exit 0; fi
[ -x "$CHROME" ] || { echo "Google Chrome not found in /Applications"; exit 1; }
"$CHROME" --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check "about:blank" >/dev/null 2>&1 &
for i in $(seq 1 20); do sleep 0.5; curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1 && { echo "job Chrome ready (profile $PROFILE)"; exit 0; }; done
echo "job Chrome did not open port 9222"; exit 1
