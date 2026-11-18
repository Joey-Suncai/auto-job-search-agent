#!/bin/bash
# Offline end-to-end gate tests for run.py (no network, no DeepSeek, no job Chrome).
# Mock forms are generated from test/app_fake/plan.json by test/make_mock.py.
# Every case's STATUS is asserted; exit 1 if any case differs.
cd "$(dirname "$0")/.." || exit 1
PY="$PYTHON"
if [ -z "$PY" ]; then PY="$HOME/.job-agent-venv/bin/python"; fi
if [ ! -x "$PY" ]; then PY=python3; fi

# Every case runs on copies in a temp dir: the tracked fixtures (test/app_*, test/data) are inputs only and stay
# untouched, so a test run never leaves a worktree dirty (JSA-289; land.py refuses a dirty tree)
T=$(mktemp -d "${TMPDIR:-/tmp}/jsa_t_run.XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
for d in app_fake app_bad app_notready; do cp -R "test/$d" "$T/$d"; done
rm -f "$T"/app_*/*.png "$T"/app_*/application_record.md "$T"/app_*/decisions.jsonl "$T"/app_*/run_log.md "$T"/app_*/runtime.json "$T"/app_*/verify.json
MOCK_OUT="$T" python3 test/make_mock.py "$T/app_fake/plan.json" || exit 1
export CX_DATA="$T/data"
export JSA_NO_PUSH=1   # never a real notification from a fixture (JSA-181)
mkdir -p "$CX_DATA"
# app_nomat = app_fake without its materials manifest (material gate, JSA-002 slice 2)
cp -R "$T/app_fake" "$T/app_nomat"; rm -f "$T/app_nomat/materials_manifest.json"
# app_extrafile = app_fake + a required extra file slot (Viking-style research supplement) with no file on hand (JSA-209)
cp -R "$T/app_fake" "$T/app_extrafile"
"$PY" -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); d['fields'].append({'key':'question_999','label':'Please upload your resume and brief research supplement as a single PDF','type':'file','required':True,'options':[],'sel':'#question_999','status':'file','source':'runner'}); json.dump(d,open(p,'w'),indent=1)" "$T/app_extrafile/plan.json"
FAKE="file://$T/mock_fake.html"
REFUSED="file://$T/mock_refused.html"
CAPTCHA="file://$T/mock_captcha.html"
BADANSWER="file://$T/mock_badanswer.html"

fails=0
run() {   # run <case name> <folder> <want> [url]
  local name=$1 folder=$2 want=$3 url=$4
  if [ -z "$url" ]; then url="$FAKE"; fi
  local got
  got=$("$PY" run.py "$folder" --submit --launch --no-ladder --url "$url" 2>&1 | awk '/^STATUS/{print $2}')
  if [ "$got" = "$want" ]; then echo "PASS  $name -> $got"
  else echo "FAIL  $name -> got '$got' want '$want'"; fails=$((fails+1)); fi
}

echo "== gates =="
run "no batch approval -> blocked"      $T/app_fake blocked
printf '{"batches":[{"approved_at":"test","folders":["app_fake","app_bad","app_notready","app_nomat","app_extrafile"]}]}' > "$CX_DATA/approved_batches.json"
echo "== JSA-209: file slots and a refused submit =="
out=$("$PY" run.py $T/app_extrafile --submit --launch --no-ladder --url "$FAKE" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "needs-user" ] && grep -q "app_extrafile.*needs a file from Joey.*research supplement" "$CX_DATA/queue.md" \
   && tail -1 "$CX_DATA/results.jsonl" | grep -q '"status": "needs-user"'; then
  echo "PASS  required extra file slot without a file -> needs-user (label queued)"
else
  echo "FAIL  required extra file slot without a file -> status '$got' (want needs-user + queue line)"; fails=$((fails+1))
fi
out=$("$PY" run.py $T/app_fake --submit --launch --no-ladder --url "$REFUSED" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "failed" ] && tail -1 "$CX_DATA/results.jsonl" | grep -q 'form refused the submit' \
   && [ ! -f $T/app_fake/submitted_confirmation.png ]; then
  echo "PASS  validation errors after Submit -> failed (field named), not unconfirmed"
else
  echo "FAIL  validation errors after Submit -> status '$got' (want failed)"; fails=$((fails+1))
fi
rm -f $T/app_fake/*.png $T/app_fake/submit_errors.json
run "approved + all gates -> submitted" $T/app_fake submitted
run "guard: rerun -> already-submitted" $T/app_fake already-submitted
run "planned field missing -> blocked"  $T/app_bad   blocked
run "plan.ready false -> needs-user (JSA-235: an answer Joey owes)" $T/app_notready needs-user
out=$("$PY" run.py $T/app_nomat --submit --launch --no-ladder --url "$FAKE" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "blocked" ] && printf '%s' "$out" | grep -q "materials gate (block)"; then
  echo "PASS  no materials manifest -> blocked by the material gate"
else
  echo "FAIL  no materials manifest -> status '$got' (want blocked by the material gate)"; fails=$((fails+1))
fi
rm -f $T/app_fake/*.png
run "captcha present -> hand-off"       $T/app_fake captcha "$CAPTCHA"

echo "== canonical audit =="
rm -f $T/app_fake/*.png
out=$("$PY" run.py $T/app_fake --submit --launch --no-ladder --url "$BADANSWER" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "blocked" ] && printf '%s' "$out" | grep -q "canonical audit FAILED"; then
  echo "PASS  wrong answer on the page -> blocked by canonical audit"
else
  echo "FAIL  wrong answer on the page -> status '$got' (want blocked + canonical audit)"; fails=$((fails+1))
fi

echo "== JSA-196: the common closing books =="
if grep '"status": "submitted"' "$CX_DATA/results.jsonl" | tail -1 | grep -q '"ats": "greenhouse".*"phases".*"tenant"' \
   && cat "$CX_DATA"/fields/*.jsonl 2>/dev/null | grep -q '"ats": "greenhouse"' \
   && [ "$(grep -c '"status": "submitted"' "$CX_DATA/results.jsonl")" -eq 1 ]; then
  echo "PASS  submitted run -> one results line with ats / phases / tenant + fields.jsonl lines"
else
  echo "FAIL  common closing books missing (results line keys / fields.jsonl)"; fails=$((fails+1))
fi
echo
if [ "$fails" -eq 0 ]; then echo "ALL GATE TESTS PASS"; else echo "$fails GATE TEST(S) FAILED"; fi
exit $fails