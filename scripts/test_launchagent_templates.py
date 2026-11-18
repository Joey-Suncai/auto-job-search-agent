"""LaunchAgent templates: launchd kills the process group of a job when it exits (JSA-378).

Error class: a job whose script backgrounds a long-lived child (`cmd &`) and then exits loses that child at once.
Every template must either set AbandonProcessGroup, or its script must not background (exec the child instead).
"""
import plistlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = sorted((REPO / "scripts" / "launchagent").glob("*.plist"))
# a trailing single '&' (not '&&', not '2>&1')
BG = re.compile(r"(?<![&>])&\s*(#.*)?$")


def load(p):
    return plistlib.loads(p.read_text().replace("{{REPO}}", str(REPO)).replace("{{", "X").replace("}}", "X").encode())


def commands(d):
    """Shell text each job runs: the -lc string and any script file it names."""
    texts = []
    for arg in d["ProgramArguments"]:
        texts.append(arg)
        f = Path(arg)
        if f.suffix == ".sh" and f.exists():
            texts.append(f.read_text())
    return "\n".join(texts)


def backgrounds(text):
    return [l for l in text.splitlines() if not l.lstrip().startswith("#") and BG.search(l.rstrip())]


def check(d, text):
    if d.get("AbandonProcessGroup"):
        return None
    bad = backgrounds(text)
    return f"{d['Label']}: backgrounds a child ({bad[0].strip()[:60]}) without AbandonProcessGroup" if bad else None


def main():
    assert TEMPLATES, "no templates found"
    errs = [e for p in TEMPLATES if (e := check(load(p), commands(load(p))))]
    # the checker itself catches the JSA-378 shape
    assert check({"Label": "x"}, '"$C" --flag >/dev/null 2>&1 &\nsleep 1'), "checker missed a backgrounded child"
    assert not check({"Label": "x"}, 'exec "$C" --flag\ncd a && b'), "checker false positive"
    # chrome is supervised by launchd, not polled by a timer
    chrome = load(REPO / "scripts/launchagent/com.jobagent.chrome.plist")
    if chrome.get("KeepAlive") != {"SuccessfulExit": False} or "StartInterval" in chrome:
        errs.append("com.jobagent.chrome must use KeepAlive{SuccessfulExit=false} and no StartInterval")
    if chrome.get("ThrottleInterval", 0) < 10:
        errs.append("com.jobagent.chrome needs ThrottleInterval >= 10")
    script = Path(chrome["ProgramArguments"][1])
    if 'exec "$CHROME"' not in script.read_text():
        errs.append(f"{script.name} must exec Chrome (launchd supervises it)")
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    print(f"ok: {len(TEMPLATES)} templates")


if __name__ == "__main__":
    main()
