"""Every Python file in scripts/ and skills/ compiles (JSA-265: a JSA-259 comment swallowed an argument in run_daily.py,
release.py's tests passed, and the email / refresh / gate routines crashed on import). Prints `fails 0` when all pass."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bad = []
for top in ("scripts", "skills", "config"):
    for d, dirs, files in os.walk(os.path.join(ROOT, top)):
        dirs[:] = [x for x in dirs if x not in ("node_modules", "__pycache__", ".venv") and not x.startswith("_bak")]
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(d, f)
                try:
                    compile(open(p, encoding="utf-8").read(), p, "exec")
                except (SyntaxError, ValueError) as e:
                    bad.append(f"{os.path.relpath(p, ROOT)}: {type(e).__name__} {str(e)[:160]}")
for b in bad:
    print("FAIL", b)
print(f"fails {len(bad)}")
sys.exit(1 if bad else 0)
