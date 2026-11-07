#!/bin/bash
# One-time setup on macOS (JSA-079). Safe to re-run: it never overwrites your own config/ files or loaded routines
# unless you pass the flag for it.
#   ./setup.sh                 check tools, create the venv, install packages, copy the config/ examples, enable the git hooks
#   ./setup.sh --agents        … and write the LaunchAgent plists to ~/Library/LaunchAgents (not loaded)
#   ./setup.sh --agents --load … and load them (the daily routines start on their schedule)
#   ./setup.sh --smoke         … and run one offline smoke test (profile, form rules, dashboard build)
# Env: JSA_VENV (default ~/.job-agent-venv) · JSA_PYTHON (python3 used to create the venv)
set -u
cd "$(dirname "$0")"
REPO="$(pwd)"
VENV="${JSA_VENV:-$HOME/.job-agent-venv}"
ok() { echo "  ✓ $*"; }; warn() { echo "  ! $*"; }; step() { echo; echo "== $*"; }
has() { for x in "${ARGS[@]:-}"; do [ "$x" = "$1" ] && return 0; done; return 1; }
ARGS=("$@")

step "tools"
[ "$(uname)" = "Darwin" ] || { echo "macOS only (launchd, Keychain, Messages)"; exit 1; }
PY="${JSA_PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    p=$(command -v $c 2>/dev/null) || continue
    $p -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && { PY=$p; break; }
  done
fi
[ -n "$PY" ] || { echo "need Python ≥ 3.10 (brew install python@3.13)"; exit 1; }
ok "python: $PY ($($PY --version 2>&1))"
command -v git >/dev/null && ok "git" || { echo "need git"; exit 1; }
command -v node >/dev/null && ok "node $(node -v)" || warn "node not found — optional (tests, cover letters); form rules then run inside Chrome"
[ -x /opt/homebrew/bin/soffice ] || command -v soffice >/dev/null && ok "LibreOffice (PDF conversion)" || warn "LibreOffice not found — needed for resume PDFs (brew install --cask libreoffice)"
[ -d "/Applications/Google Chrome.app" ] && ok "Google Chrome" || warn "Google Chrome not found — the form runners drive it"

step "python venv $VENV"
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV" || { echo "venv failed"; exit 1; }
"$VENV/bin/python" -m pip install -q --upgrade pip >/dev/null 2>&1
if "$VENV/bin/python" -m pip install -q -r requirements.txt >/tmp/jsa-pip.log 2>&1; then ok "packages from requirements.txt"
else echo "pip failed — last lines:"; tail -15 /tmp/jsa-pip.log; exit 1; fi
if command -v npm >/dev/null; then
  npm install --silent --no-audit --no-fund >/tmp/jsa-npm.log 2>&1 && ok "node packages (package.json)" || warn "npm install failed (see /tmp/jsa-npm.log) — optional"
fi

step "your data (config/)"
for ex in config/*.example.*; do
  mine="${ex/.example/}"
  if [ -e "$mine" ]; then ok "$(basename "$mine") exists — kept"
  else cp "$ex" "$mine"; warn "$(basename "$mine") created from the example — replace it with YOUR facts (config/README.md)"; fi
done
mkdir -p data/store data/runner applications
"$PY" skills/auto-apply/scripts/build_bundle.py >/dev/null && ok "cx_bundle.js built from your profile (rebuild after editing config/profile.json)"

step "git hooks"
git rev-parse --git-dir >/dev/null 2>&1 && git config core.hooksPath .githooks && ok "core.hooksPath = .githooks (pre-commit companion-file check)" || warn "not a git checkout — hooks skipped"

step "secrets (macOS Keychain — the agent never sees them in a file)"
GMAIL=$("$PY" -c "import sys; sys.path.insert(0, 'config'); import jsa_profile; print(jsa_profile.get('accounts.gmail') or '')")
kc() { security find-generic-password -s "$1" >/dev/null 2>&1 && ok "$1 in Keychain" || warn "$1 missing — $2"; }
kc jobagent-gmail "Gmail app password for the e-mail check: security add-generic-password -s jobagent-gmail -a \"$GMAIL\" -w"
kc job-agent-gmail "same app password for sign-in codes: security add-generic-password -s job-agent-gmail -a \"$GMAIL\" -w"
kc jobagent-anthropic "optional, Claude reads job mail: security add-generic-password -s jobagent-anthropic -a anthropic -w"
kc jobagent-workday "optional, Workday sign-in: security add-generic-password -s jobagent-workday -a \"$GMAIL\" -w"
[ -f "${DEEPSEEK_KEY_FILE:-$HOME/deepseek/api_key}" ] && ok "DeepSeek key file" || warn "optional: DeepSeek API key in ~/deepseek/api_key (tailored materials)"

if has --agents; then
  step "LaunchAgents"
  "$PY" scripts/launchagent/install.py --python "$PY" --venv-python "$VENV/bin/python" $(has --load && echo --load)
fi

if has --smoke; then
  step "smoke test (offline)"
  "$PY" -c "import sys; sys.path.insert(0, 'config'); import jsa_profile; p = jsa_profile.load(); print('  profile:', jsa_profile.path(), '·', p['name']['full'])" || exit 1
  if command -v node >/dev/null; then
    node -e "const {answerFor}=require('./skills/auto-apply/scripts/answer_rules.js'); const a=answerFor({l:'First name'}); if(a.status!=='ok') process.exit(1); console.log('  form rules: First name →', a.value)" || exit 1
  fi
  "$PY" scripts/dashboard/build_dash.py >/dev/null && ok "dashboard built: dashboard/index.html" || warn "dashboard build failed"
fi

step "done"
echo "  Next: fill config/profile.json (and the other config/ files) with your own facts, then: ./setup.sh --agents --load"
