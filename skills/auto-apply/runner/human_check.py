#!/usr/bin/env python3
"""Hand-off for human checks / CAPTCHAs (JSA-106, Joey 2026-11-03 「改交接」). A check is always Joey's — nothing here
reads, ranks or answers one. It only makes the hand-off fast:
  1. message(): the push names the company and carries the question text and its options, so Joey sees from his phone
     what waits for him;
  2. park(): the check goes into data/runner/human_checks.jsonl, the tab stays open, and the runner moves on to the next
     application instead of waiting; after Joey answers in the tab, `--attach` continues that application;
  3. pending() / --list: every open check in one list after the batch (--push sends it as one notification).
A run that ends without a check (submitted, blocked, …) closes its folder's open check (resolve()).

    ~/.job-agent-venv/bin/python human_check.py --list [--push]     # open checks, oldest first
    ~/.job-agent-venv/bin/python human_check.py --done <folder>     # close one by hand (Joey submitted it himself, gave up, …)
"""
import argparse, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')


def now():
    return datetime.now().isoformat(timespec='seconds')


def ledger():
    return os.path.join(DATA, 'human_checks.jsonl')


def company(folder):
    """'2026-11-03_FHLB_Indy_Analyst' → 'FHLB Indy Analyst' (the date prefix dropped)."""
    b = os.path.basename(os.path.abspath(folder))
    return (b[11:] if len(b) > 11 and b[10] == '_' else b).replace('_', ' ')[:60]


def message(folder, checks, parked=True):
    """Pure (tested). (title, body) for one application's checks: company, each question in full with its options, where
    to answer. checks = [{'question': str, 'options': [str]}]; an empty question = an image / widget CAPTCHA. parked=False:
    the runner waits in place for Joey."""
    lines = [company(folder)]
    for c in checks[:3]:
        q = ' '.join(str(c.get('question') or '').split())
        lines.append('· ' + (q[:200] if q else '图片 / 勾选验证（CAPTCHA）'))
        opts = [' '.join(str(o).split()) for o in (c.get('options') or []) if str(o).strip()]
        if opts: lines.append('  选项：' + ' / '.join(o[:40] for o in opts[:8]) + (' …' if len(opts) > 8 else ''))
    lines.append('请在 job Chrome 的标签页里完成；' + ('runner 已先去投下一份，回头接着交这一份。' if parked else 'runner 在等，做完自动继续。'))
    return '求职 runner：人机验证（等你）', '\n'.join(lines)


def _rows():
    try:
        return [json.loads(l) for l in open(ledger(), encoding='utf-8') if l.strip()]
    except FileNotFoundError:
        return []


def pending(rows=None):
    """Pure over rows (tested). Open checks, oldest first: a folder's latest row decides (open → listed, resolved → not)."""
    last = {}
    for r in (_rows() if rows is None else rows):
        last.pop(r['folder'], None); last[r['folder']] = r    # re-insert so the order follows the latest event
    return sorted((r for r in last.values() if r.get('state') == 'open'), key=lambda r: r.get('at', ''))


def _append(row):
    os.makedirs(DATA, exist_ok=True)
    with open(ledger(), 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def park(folder, ats, url, checks, notify=True):
    """Record the open check and push one message; the caller keeps the tab and ends this run."""
    _append({'at': now(), 'folder': os.path.basename(os.path.abspath(folder)), 'ats': ats, 'url': url, 'state': 'open',
             'checks': [{'question': c.get('question') or '', 'options': list(c.get('options') or [])[:20]} for c in checks]})
    if notify: push(*message(folder, checks))


def resolve(folder, how):
    """Close the folder's open check (no-op when there is none)."""
    b = os.path.basename(os.path.abspath(folder))
    if any(r['folder'] == b for r in pending()):
        _append({'at': now(), 'folder': b, 'state': 'resolved', 'how': how})


def summary(rows):
    """Pure (tested). (title, body) listing every open check; None when there is none."""
    if not rows: return None
    body = []
    for r in rows:
        qs = [' '.join(str(c.get('question') or '').split())[:80] or 'CAPTCHA' for c in r.get('checks') or []] or ['CAPTCHA']
        body.append(f"· {company(r['folder'])} ({r.get('ats', '')}): " + ' | '.join(qs))
    return f'求职 runner：{len(rows)} 个人机验证等你', '\n'.join(body) + '\n都在 job Chrome 的标签页里；做完告诉我，我接着交。'


def push(title, body):
    """Phone + Mac push (scripts/daily/notify.py); never fails the run."""
    try:
        import subprocess
        subprocess.run(['/opt/homebrew/bin/python3', os.path.join(ROOT, 'scripts', 'daily', 'notify.py'), title, body[:600]],
                       capture_output=True, timeout=40)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true'); ap.add_argument('--push', action='store_true'); ap.add_argument('--done')
    a = ap.parse_args()
    if a.done:
        resolve(a.done, 'by hand'); print('closed', os.path.basename(os.path.abspath(a.done)))
    rows = pending()
    if a.list or not a.done:
        if not rows: print('no open human checks')
        for r in rows:
            print(f"{r['at']}  {r['folder']}  [{r.get('ats', '')}]  {r.get('url', '')}")
            for c in r.get('checks') or []:
                print('    ' + (c.get('question') or 'CAPTCHA (image / widget)')[:160] + (('  · ' + ' / '.join(c['options'][:8])) if c.get('options') else ''))
    if a.push and rows:
        push(*summary(rows))


if __name__ == '__main__':
    sys.exit(main())
