#!/bin/bash
# Run every offline test in one go (JSA-080). Exit 0 = all passed. No network, no DeepSeek, no job Chrome.
#   scripts/test_all.sh            Python + Node + the runner's offline end-to-end gate (t_run.sh)
#   scripts/test_all.sh --quick    skip t_run.sh (the slowest, ~1 min)
# Python = $JSA_VENV/bin/python (default ~/.job-agent-venv), else python3. Node tests are skipped when node is missing.
# Not run here: t_browser.js and real_check_*.js (they need a live browser / real pages).
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
PY="${JSA_VENV:-$HOME/.job-agent-venv}/bin/python"; [ -x "$PY" ] || PY=python3
# tests never touch the live data home (ADR-0008 / ADR-0011): they run on an APFS clone of it (copy-on-write, ~3 s, removed
# at exit) — so they test the user's current facts, and the repo holds no fact copies. JSA_TEST_HOME = use that folder
# instead; no data home (an open-source checkout) → this checkout with the fictional fixture below.
if [ -z "${JSA_TEST_HOME:-}" ] && [ ! -f .jsa-public ]; then
  LIVE=$(cat "$HOME/.config/job-search-agent/home" 2>/dev/null); LIVE="${LIVE/#\~/$HOME}"
  if [ -n "$LIVE" ] && [ -d "$LIVE/config" ]; then
    JSA_TEST_HOME=$(mktemp -d "${TMPDIR:-/tmp}/jsa_test_home.XXXXXX")
    for d in config facts resume data applications; do
      [ -e "$LIVE/$d" ] || continue; cp -cR "$LIVE/$d" "$JSA_TEST_HOME/" 2>/dev/null || cp -R "$LIVE/$d" "$JSA_TEST_HOME/"
    done
    CLONED=1
    echo "== test home: clone of $LIVE"
    # JSA-403: the repo's tests state a fictional identity (config/fixtures/fake_identity.json); the clone keeps the user's real
    # answers but carries that identity, so the user's own name / address / e-mail / phone never need to appear in a test
    python3 scripts/fake_identity.py --home "$JSA_TEST_HOME" || { rm -rf "$JSA_TEST_HOME"; exit 1; }
    export JSA_REAL_HOME="$LIVE"      # test_no_personal_facts scans the repo for the LIVE profile's values
  fi
fi
export JSA_HOME="${JSA_TEST_HOME:-$ROOT}"
# the browser bundle from THIS checkout's code + the test home's profile (t_jsdom.js reads it there)
[ "$JSA_HOME" != "$ROOT" ] && python3 skills/auto-apply/scripts/build_bundle.py >/dev/null 2>&1
# tests never push to Joey (JSA-181: t_run.sh's fake CAPTCHA for app_fake reached him after every release)
export JSA_NO_PUSH=1
# public tree (.jsa-public, written by the export): tests run against the fictional F-1 fixture, whatever the user's own
# config/ says; the private repo tests the real config/ files (JSA-086)
if { [ -f .jsa-public ] || [ "$JSA_HOME" = "$ROOT" ]; } && [ -d config/fixtures/f1_student ]; then
  export JSA_PROFILE="$ROOT/config/fixtures/f1_student/profile.json" JSA_CANONICAL="$ROOT/config/fixtures/f1_student/canonical.json" \
         JSA_WD_PROFILE="$ROOT/config/fixtures/f1_student/wd_profile.json"
  echo "== test profile: config/fixtures/f1_student (fictional F-1 student)"
fi
pass=0; failed=()
OUT=$(mktemp "${TMPDIR:-/tmp}/jsa_test_out.XXXXXX"); trap 'rm -f "$OUT"; [ -n "${JSA_TEST_HOME:-}" ] && [ -n "${CLONED:-}" ] && rm -rf "$JSA_TEST_HOME"' EXIT
run() {   # run <dir> <cmd…>: one test, from its own folder. A failing test's WHOLE output goes into the log (JSA-380: a
          # flaky failure used to leave only the summary line — the failing case was lost). Own temp file per run, not a shared /tmp name.
  local dir="$1"; shift
  if (cd "$dir" && "$@" >"$OUT" 2>&1); then pass=$((pass + 1))
  else failed+=("$dir/${*: -1}"); echo "FAIL $dir/${*: -1}"; sed 's/^/     | /' "$OUT"; fi
}

echo "== Python ($PY)"
while IFS= read -r t; do
  run "$(dirname "$t")" "$PY" "$(basename "$t")"
done < <(find scripts skills -type f \( -name 't_*.py' -o -name 'test_*.py' -o -name '_test_*.py' \) \
           -not -path '*/_bak*' -not -path '*/node_modules/*' -not -path '*/test_cases/*' | sort)

if command -v node >/dev/null; then
  echo "== Node ($(node -v))"
  while IFS= read -r t; do
    case "$(basename "$t")" in t_browser.js|real_check_*) continue;; esac
    if [ "$(basename "$t")" = t_jsdom.js ] && ! node -e "require.resolve('jsdom')" >/dev/null 2>&1; then echo "skip $t (npm install for jsdom)"; continue; fi
    run "$(dirname "$t")" node "$(basename "$t")"
  done < <(find scripts skills -type f \( -name 't_*.js' -o -name 'test_*.js' -o -name '*_test.js' \) \
             -not -path '*/_bak*' -not -path '*/node_modules/*' | sort)
else
  echo "== Node: not installed — JS tests skipped"
fi

if [ "${1:-}" != "--quick" ] && [ -f skills/auto-apply/runner/test/t_run.sh ]; then
  echo "== runner end-to-end (t_run.sh)"
  PYTHON="$PY" run skills/auto-apply/runner/test bash t_run.sh
fi

echo
if [ ${#failed[@]} -eq 0 ]; then echo "ALL PASS ($pass tests)"; exit 0; fi
echo "${#failed[@]} FAILED, $pass passed:"; printf '  %s\n' "${failed[@]}"; exit 1
