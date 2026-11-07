#!/usr/bin/env python3
"""Lever one-click fill for Joey's OWN Chrome (JSA-058, 2026-10-31).

Lever's hCaptcha challenges every submit from the job Chrome (10 of 10 on 2026-10-31), and a CAPTCHA is always Joey's
(rule 7) — never solved or bypassed by the agent. So the runner fills and reads back the form in the job Chrome (dry-run),
and Joey submits in his normal Chrome. This server + the small extension in ./extension turn his part into: open the
apply page → click "Fill from job agent" → look → Submit (and solve a challenge himself if one appears).

The server binds 127.0.0.1 only and serves, for a Lever apply URL, the answers the runner already filled AND read back
(form_check.json, every field ok, no problems) plus the files (base64). When the extension sees Lever's /thanks page it
calls /submitted and the server records it exactly like `sync_results.py --manual` (results line by: joey + tracker row).

    python3 skills/auto-apply/lever_fill/server.py            # from the main folder; Ctrl-C to stop
Spec + DeepSeek-written cases: scripts/test_cases/lever_fill_*; harness scripts/test_lever_fill.py.
"""
import base64, glob, json, os, re, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
APPS = jpaths.apps()
PORT = 8765
POSTING = re.compile(r'jobs\.(?:eu\.)?lever\.co/([\w.-]+)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', re.I)


def posting_id(url):
    m = POSTING.search(url or '')
    return (m.group(1).lower(), m.group(2).lower()) if m else None


def close_job_chrome_tabs(pid, cdp='http://127.0.0.1:9222', wait=2.0):
    """After Joey's submit is recorded: close every job-Chrome tab of that posting (its /thanks and dry-run copies) through
    the DevTools HTTP endpoint. Joey 2026-11-04: 「是要成功提交之后关掉。」 Edge has no debugging port, so his Edge tab stays
    (JSA-145). Returns the number closed; never raises."""
    time.sleep(wait)                                  # let the extension's request finish first
    n = 0
    try:
        for t in json.load(urllib.request.urlopen(cdp + '/json/list', timeout=5)):
            if t.get('type') == 'page' and pid and pid in (t.get('url') or ''):
                urllib.request.urlopen(f"{cdp}/json/close/{t['id']}", timeout=5).read(); n += 1
    except Exception:
        pass
    return n


def payload(plan, check, submitted):
    """Pure (tested): plan.json + form_check.json of one folder → (data, None) or (None, reason).
    data = {fields: [{key, type, value}] in plan order without files, files: [{key, name}]}."""
    if submitted:
        return None, 'already submitted'
    if (plan or {}).get('ats') != 'lever':
        return None, 'not a Lever folder'
    if not check or not check.get('fields'):
        return None, 'no dry-run read-back yet (run run_form.py first)'
    if check.get('problems'):
        return None, 'the dry-run had problems: ' + '; '.join(check['problems'])[:200]
    if not all(f.get('ok') for f in check['fields']):
        return None, 'a field did not read back: ' + ', '.join(f.get('key', '') for f in check['fields'] if not f.get('ok'))[:200]
    by = {f.get('key'): f for f in check['fields']}
    order = [f.get('key') for f in plan.get('fields', [])] + [k for k in by if k not in [f.get('key') for f in plan.get('fields', [])]]
    fields, files = [], []
    for k in order:
        f = by.get(k)
        if not f or f.get('want') in (None, ''):
            continue
        if f.get('type') == 'file':
            files.append({'key': k, 'name': f['want']})
        else:
            fields.append({'key': k, 'type': f.get('type') or 'text', 'value': str(f['want'])})
    return {'fields': fields, 'files': files}, None


RUNNER_MARK = 'runner_active.json'   # written by runner/run_form.py for the whole run (JSA-083)
RUNNER_MAX_AGE = 2 * 3600            # a mark older than this is stale whatever its pid says


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)                       # signal 0 = existence check only
        return True
    except PermissionError:
        return True
    except (OSError, ValueError, TypeError):
        return False


def runner_owns(mark, now_ts, alive=pid_alive):
    """Pure (tested, JSA-083): True when run_form.py is working on this folder right now, so the page in front of the
    extension is the RUNNER's (the extension is installed in the job Chrome too): its /thanks is the runner's submit
    (the runner writes its own results line, by: runner) and its form is the runner's to fill. mark = the folder's
    runner_active.json (dict) or None. Owned = a mark with a numeric ts no older than RUNNER_MAX_AGE (and not in the
    future by more than a minute) whose pid is still running."""
    if not isinstance(mark, dict):
        return False
    ts = mark.get('ts')
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return False
    age = now_ts - ts
    if age > RUNNER_MAX_AGE or age < -60:
        return False
    return bool(mark.get('pid')) and bool(alive(mark.get('pid')))


def read_mark(folder):
    try:
        return json.load(open(os.path.join(folder, RUNNER_MARK), encoding='utf-8'))
    except Exception:
        return None


def find_folder(url):
    pid = posting_id(url)
    if not pid:
        return None
    for p in sorted(glob.glob(os.path.join(APPS, '*', 'plan.json')), reverse=True):
        try:
            if posting_id(json.load(open(p, encoding='utf-8')).get('url')) == pid:
                return os.path.dirname(p)
        except Exception:
            continue
    return None


def submitted_folders():
    p = jpaths.data('runner', 'results.jsonl')
    return {json.loads(l).get('folder') for l in open(p, encoding='utf-8') if l.strip() and '"submitted"' in l} if os.path.exists(p) else set()


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def log_message(self, fmt, *a):
        sys.stderr.write('lever_fill: ' + (fmt % a) + '\n')

    def do_GET(self):
        u = urlsplit(self.path); q = parse_qs(u.query); url = (q.get('url') or [''])[0]
        folder = find_folder(url)
        if u.path == '/health':
            return self._send(200, {'ok': True})
        if self.headers.get('X-Lever-Fill') != '1':   # only the extension sends it: a web page cannot add a custom header
            return self._send(403, {'error': 'missing X-Lever-Fill header'})   # cross-site without a CORS preflight, which we never answer
        if not folder:
            return self._send(404, {'error': 'no application folder for this posting'})
        name = os.path.basename(folder)
        if runner_owns(read_mark(folder), time.time()):    # JSA-083: the runner's own tab in the job Chrome — never fill or record it
            if u.path == '/submitted':
                return self._send(200, {'recorded': False, 'by': 'runner', 'folder': name,
                                        'note': 'submitted by the runner — it records the result itself'})
            return self._send(409, {'error': 'the runner is working on this form right now', 'by': 'runner', 'folder': name})
        if u.path == '/lever':
            try:
                plan = json.load(open(os.path.join(folder, 'plan.json'), encoding='utf-8'))
                check = json.load(open(os.path.join(folder, 'form_check.json'), encoding='utf-8'))
            except Exception as e:
                return self._send(409, {'error': f'missing plan / form_check: {e}', 'folder': name})
            data, why = payload(plan, check, name in submitted_folders())
            if why:
                return self._send(409, {'error': why, 'folder': name})
            for f in data['files']:
                fp = os.path.join(folder, f['name'])
                f['b64'] = base64.b64encode(open(fp, 'rb').read()).decode() if os.path.exists(fp) else None
            data['folder'] = name
            return self._send(200, data)
        if u.path == '/submitted':                   # Lever /thanks page seen in Joey's Chrome → record it
            sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
            import sync_results
            try:
                rc = sync_results.manual(name, 'submitted by Joey in his Chrome (one-click fill, lever_fill)', None, print)
            except SystemExit as e:
                rc = e.code
            threading.Thread(target=close_job_chrome_tabs, args=((posting_id(url) or ("", ""))[1],), daemon=True).start()
            return self._send(200, {'recorded': rc is not None, 'folder': name})
        return self._send(404, {'error': 'unknown path'})


if __name__ == '__main__':
    print(f'lever_fill: http://127.0.0.1:{PORT} (applications in {APPS}) — Ctrl-C to stop')
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
