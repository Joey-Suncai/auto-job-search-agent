#!/bin/bash
# Run every offline test in one go (JSA-080). Exit 0 = all passed. No network, no DeepSeek, no job Chrome.
#   scripts/test_all.sh            Python + Node + the runner's offline end-to-end gate (t_run.sh)
#   scripts/test_all.sh --quick    skip t_run.sh (the slowest, ~1 min)
# Python = $JSA_VENV/bin/python (default ~/.job-agent-venv), else python3. Node tests are skipped when node is missing.
# Not run here: t_browser.js and real_check_*.js (they need a live browser / real pages).
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
PY="${JSA_VENV:-$HOME/.job-agent-venv}/bin/python"; [ -x "$PY" ] || PY=python3
# tests never touch the live data home (ADR-0008): they use this checkout's own files, whatever the pointer file says
export JSA_HOME="${JSA_TEST_HOME:-$ROOT}"
# tests never push to Joey (JSA-181: t_run.sh's fake CAPTCHA for app_fake reached him after every release)
export JSA_NO_PUSH=1
# public tree (.jsa-public, written by the export): tests run against the fictional F-1 fixture, whatever the user's own
# config/ says; the private repo tests the real config/ files (JSA-086)
if [ -f .jsa-public ] && [ -d config/fixtures/f1_student ]; then
  export JSA_PROFILE="$ROOT/config/fixtures/f1_student/profile.json" JSA_CANONICAL="$ROOT/config/fixtures/f1_student/canonical.json" \
         JSA_WD_PROFILE="$ROOT/config/fixtures/f1_student/wd_profile.json"
  echo "== test profile: config/fixtures/f1_student (fictional F-1 student)"
fi
pass=0; failed=()
run() {   # run <dir> <cmd…>: one test, from its own folder
  local dir="$1"; shift
  if (cd "$dir" && "$@" >/tmp/jsa_test.out 2>&1); then pass=$((pass + 1))
  else failed+=("$dir/${*: -1}"); echo "FAIL $dir/${*: -1}"; tail -5 /tmp/jsa_test.out | sed 's/^/     /'; fi
}
# t_run.sh rewrites its tracked fixtures: put them back afterwards when they were clean before
FIX="skills/auto-apply/runner/test/app_bad skills/auto-apply/runner/test/app_fake skills/auto-apply/runner/test/app_notready skills/auto-apply/runner/test/data"
clean_fix=0; git rev-parse --git-dir >/dev/null 2>&1 && [ -z "$(git status --porcelain -- $FIX 2>/dev/null)" ] && clean_fix=1

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
  [ $clean_fix = 1 ] && git checkout -q -- $FIX 2>/dev/null
fi

echo
if [ ${#failed[@]} -eq 0 ]; then echo "ALL PASS ($pass tests)"; exit 0; fi
echo "${#failed[@]} FAILED, $pass passed:"; printf '  %s\n' "${failed[@]}"; exit 1
