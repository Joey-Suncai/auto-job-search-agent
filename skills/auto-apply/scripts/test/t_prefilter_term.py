"""prefilter.term_range / START flag (JSA-033). Prints `fails 0` when everything passes."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import prefilter as p

fails = 0
def ok(c, label):
    global fails
    fails += 0 if c else 1
    print(("PASS " if c else "FAIL ") + label)

ok(p.term_range("Status: Intern, Full-Time Duration: 3 Months (January - March 2027)"), "Hitachi January - March 2027 → term")
ok(p.term_range("Internship dates: Sep 8, 2026 – Dec 11, 2026"), "fall dated range → term")
ok(p.term_range("runs Jan 5 to Apr 30, 2027"), "Jan 5 to Apr 30, 2027 → term")
ok(not p.term_range("Program dates: June 1 - August 14, 2027"), "summer range is fine")
ok(not p.term_range("Internship runs May 2027 to August 2027"), "May–Aug is fine")
ok(not p.term_range("expected graduation date of December 2027 - May 2028"), "graduation window is not a term")
ok(not p.term_range("Applications open September - November 2026"), "application window is not a term")
job = {"level": "Internship", "title": "Research Intern", "company": "Hitachi"}
jd = {"status": "ok", "text": "x " * 300 + "Duration: 3 Months (January - March 2027)"}
ok("START" in p.flags_of(job, jd, set(), set()), "flags_of marks START")
F = p.flags_of({"level": "Internship", "title": "Data Analyst Intern", "company": "Corquinnev US"}, jd | {"text": "x " * 300 + "Summer 2027"}, {"corquinnev"}, set())
ok("APPLIED" in F and not [f for f in F if f not in p.SOFT], "another role at an applied company: soft APPLIED flag, not dropped")
print(f"fails {fails}")
sys.exit(1 if fails else 0)
