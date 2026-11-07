#!/bin/bash
# Offline end-to-end gate tests for run.py (no network, no DeepSeek, no job Chrome).
# Mock forms are generated from test/app_fake/plan.json by test/make_mock.py.
# Every case's STATUS is asserted; exit 1 if any case differs.
cd "$(dirname "$0")/.." || exit 1
PY="$PYTHON"
if [ -z "$PY" ]; then PY="$HOME/.job-agent-venv/bin/python"; fi
if [ ! -x "$PY" ]; then PY=python3; fi

python3 test/make_mock.py || exit 1
export CX_DATA="$PWD/test/data"
export JSA_NO_PUSH=1   # never a real notification from a fixture (JSA-181)
rm -rf "$CX_DATA"; mkdir -p "$CX_DATA"
rm -f test/app_fake/*.png test/app_fake/application_record.md test/app_bad/*.png test/app_notready/*.png test/app_*/decisions.jsonl
# app_nomat = app_fake without its materials manifest (material gate, JSA-002 slice 2)
rm -rf test/app_nomat; cp -R test/app_fake test/app_nomat; rm -f test/app_nomat/materials_manifest.json
# app_extrafile = app_fake + a required extra file slot (Viking-style research supplement) with no file on hand (JSA-209)
rm -rf test/app_extrafile; cp -R test/app_fake test/app_extrafile
"$PY" -c "import json,sys; p='test/app_extrafile/plan.json'; d=json.load(open(p)); d['fields'].append({'key':'question_999','label':'Please upload your resume and brief research supplement as a single PDF','type':'file','required':True,'options':[],'sel':'#question_999','status':'file','source':'runner'}); json.dump(d,open(p,'w'),indent=1)"
FAKE="file://$PWD/test/mock_fake.html"
REFUSED="file://$PWD/test/mock_refused.html"
CAPTCHA="file://$PWD/test/mock_captcha.html"
BADANSWER="file://$PWD/test/mock_badanswer.html"

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
run "no batch approval -> blocked"      test/app_fake blocked
printf '{"batches":[{"approved_at":"test","folders":["app_fake","app_bad","app_notready","app_nomat","app_extrafile"]}]}' > "$CX_DATA/approved_batches.json"
echo "== JSA-209: file slots and a refused submit =="
out=$("$PY" run.py test/app_extrafile --submit --launch --no-ladder --url "$FAKE" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "needs-user" ] && grep -q "app_extrafile.*needs a file from Joey.*research supplement" "$CX_DATA/queue.md" \
   && tail -1 "$CX_DATA/results.jsonl" | grep -q '"status": "needs-user"'; then
  echo "PASS  required extra file slot without a file -> needs-user (label queued)"
else
  echo "FAIL  required extra file slot without a file -> status '$got' (want needs-user + queue line)"; fails=$((fails+1))
fi
out=$("$PY" run.py test/app_fake --submit --launch --no-ladder --url "$REFUSED" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "failed" ] && tail -1 "$CX_DATA/results.jsonl" | grep -q 'form refused the submit' \
   && [ ! -f test/app_fake/submitted_confirmation.png ]; then
  echo "PASS  validation errors after Submit -> failed (field named), not unconfirmed"
else
  echo "FAIL  validation errors after Submit -> status '$got' (want failed)"; fails=$((fails+1))
fi
rm -f test/app_fake/*.png test/app_fake/submit_errors.json
run "approved + all gates -> submitted" test/app_fake submitted
run "guard: rerun -> already-submitted" test/app_fake already-submitted
run "planned field missing -> blocked"  test/app_bad   blocked
run "plan.ready false -> needs-user (JSA-235: an answer Joey owes)" test/app_notready needs-user
out=$("$PY" run.py test/app_nomat --submit --launch --no-ladder --url "$FAKE" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "blocked" ] && printf '%s' "$out" | grep -q "materials gate (block)"; then
  echo "PASS  no materials manifest -> blocked by the material gate"
else
  echo "FAIL  no materials manifest -> status '$got' (want blocked by the material gate)"; fails=$((fails+1))
fi
rm -f test/app_fake/*.png
run "captcha present -> hand-off"       test/app_fake captcha "$CAPTCHA"

echo "== canonical audit =="
rm -f test/app_fake/*.png
out=$("$PY" run.py test/app_fake --submit --launch --no-ladder --url "$BADANSWER" 2>&1)
got=$(printf '%s' "$out" | awk '/^STATUS/{print $2}')
if [ "$got" = "blocked" ] && printf '%s' "$out" | grep -q "canonical audit FAILED"; then
  echo "PASS  wrong answer on the page -> blocked by canonical audit"
else
  echo "FAIL  wrong answer on the page -> status '$got' (want blocked + canonical audit)"; fails=$((fails+1))
fi

rm -rf test/app_nomat test/app_extrafile; rm -f test/app_*/decisions.jsonl test/app_fake/submit_errors.json
echo
if [ "$fails" -eq 0 ]; then echo "ALL GATE TESTS PASS"; else echo "$fails GATE TEST(S) FAILED"; fi
exit $fails