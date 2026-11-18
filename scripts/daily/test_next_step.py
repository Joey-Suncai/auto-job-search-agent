"""Harness for next_step.py (JSA-265, rule 13): runs DeepSeek's cases (scripts/test_cases/next_step_cases.json, written
from next_step_spec.md without the code); a case recorded in next_step_verdicts.json is judged as misreading the spec
and skipped with its reason. Prints `fails 0` when everything passes."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import next_step as ns  # noqa: E402

TC = os.path.join(os.path.dirname(HERE), "test_cases")
cases = json.load(open(os.path.join(TC, "next_step_cases.json")))
vpath = os.path.join(TC, "next_step_verdicts.json")
verdicts = json.load(open(vpath)) if os.path.exists(vpath) else {}
fails = 0
for c in cases:
    if c["name"] in verdicts:
        print("SKIP", c["name"], "—", verdicts[c["name"]][:100])
        continue
    if c["fn"] == "is_vague":
        got, want = ns.is_vague(c["text"]), c["expect"]
    else:
        g = ns.rules_action(c["kind"], c["subject"], c["body"], c["date"])
        got = (g["action"], g["deadline"], g["reread"])
        want = (c["expect_action"], c["expect_deadline"], c["expect_reread"])
    if got != want:
        fails += 1
        print("FAIL", c["name"], "\n   got ", got, "\n   want", want)
    else:
        print("PASS", c["name"])
print(f"fails {fails}")
sys.exit(1 if fails else 0)
