"""Push a short message to Joey: macOS notification + iMessage to his own number (phone push, no extra account).

usage: python3 scripts/daily/notify.py "<title>" "<body>"     (exit 0 if at least one channel delivered)
The iMessage target comes from scripts/daily/notify.json {"imessage_to": "+1..."}; remove the key to stop phone pushes.
JSA_NO_PUSH=1 (any value but "" / "0") mutes every push: nothing is shown or sent, the message goes to stderr. The test
suite sets it (scripts/test_all.sh, runner/test/t_run.sh) — the runner's end-to-end test parks a fake CAPTCHA for the
fixture folder "app_fake", which reached Joey as a real notification after every release (2026-11-05, JSA-181).
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def osa(script, *args):
    return subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True, timeout=30)


def muted(env=None):
    """Pure (tested). True when JSA_NO_PUSH is set to anything but "" or "0" (surrounding spaces ignored)."""
    v = (os.environ if env is None else env).get("JSA_NO_PUSH")
    return v is not None and v.strip() not in ("", "0")


def notify(title, body):
    if muted():
        print(f"push muted (JSA_NO_PUSH): {title} | {body[:120]}", file=sys.stderr)
        return []
    sent = []
    r = osa('on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run', title, body[:200])
    if r.returncode == 0:
        sent.append("mac")
    cfg = json.load(open(os.path.join(HERE, "notify.json"))) if os.path.exists(os.path.join(HERE, "notify.json")) else {}
    to = cfg.get("imessage_to")
    if to:
        r = osa('on run argv\ntell application "Messages"\n'
                'set svc to 1st account whose service type = iMessage\n'
                'send (item 2 of argv) to participant (item 1 of argv) of svc\nend tell\nend run',
                to, f"{title}\n{body}"[:1500])
        if r.returncode == 0:
            sent.append("imessage")
        else:
            print("imessage failed:", r.stderr.strip()[:200], file=sys.stderr)
    return sent


if __name__ == "__main__":
    s = notify(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
    print("sent:", ", ".join(s) or ("nothing (muted)" if muted() else "nothing"))
    sys.exit(0 if s or muted() else 1)
