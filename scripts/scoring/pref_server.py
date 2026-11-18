#!/usr/bin/env python3
"""Dashboard 👍 / 👎 write path (JSA-101): a tiny localhost server the dashboard page POSTs to.

The dashboard is a static page (file:// or a local http.server), so it cannot write data/store/ itself. A click sends
    POST http://127.0.0.1:8766/pref   X-JSA-Pref: 1   Content-Type: application/json   {"id": "J01234", "pref": "up"}
and this server runs pref.apply() — the same code path as `scripts/scoring/pref.py` (one place sets joey_pref, re-scores
through store.save and logs to data/scoring/prefs.jsonl). It answers the new {v_level, score, tier}; the page shows it
at once and the com.jobagent.dash rebuild follows within 60 s.

Its own LaunchAgent (com.jobagent.pref), not a route on lever_fill/server.py: that one serves application data to a
browser extension for one ATS; a store writer for the dashboard is a different job, and either can be down alone.
Guards: binds 127.0.0.1 only; Host must be 127.0.0.1 / localhost (DNS rebinding); Origin must be absent, "null"
(file://) or an http://localhost / 127.0.0.1 page; the custom X-JSA-Pref header + JSON content type force a CORS
preflight, so no other web page can post here. Requests are handled one at a time (two quick clicks never race on
jobs.jsonl).

    python3 scripts/scoring/pref_server.py            # from the main folder; Ctrl-C to stop
Spec + DeepSeek-written cases: scripts/test_cases/pref_server_*; harness scripts/scoring/test_pref_server.py.

Second route (JSA-125, 2026-11-03): the tracker's Done button —
    POST /action   X-JSA-Pref: 1   Content-Type: application/json   {"job_id": "J01234", "done": true|false}
runs scripts/store/action_done.apply() (done = action_needed → action_done history; false = undo) and answers the new
row's {job_id, action_needed, action_done}. Same guards as /pref. Cases: scripts/test_cases/action_route_*.

Fourth route (JSA-406): POST /decline {job_id, give_up: true|false} — the Waiting-for-you table's Give up (and its Undo):
status → "Declined by Joey" via action_done.decline; nothing is sent to the company. Cases: scripts/test_cases/give_up_*.

Third route (JSA-179, 2026-11-05): the job detail panel's Apply button (after the page's confirm dialog) —
    POST /apply   X-JSA-Pref: 1   Content-Type: application/json   {"job_id": "J01234", "confirm": true}
runs scripts/store/apply_req.queue() (checks: 可投, not in the tracker, not requested yet, not on the skip list, a runner
that can submit) and answers {job_id, apply_req, apply_req_at}; a refusal is 409 with the reason. The open Claude
session picks the request up (apply_req.py --watch). Same guards. Cases: scripts/test_cases/apply_route_*.
"""
import json, os, re, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PORT = 8766
MAX_BODY = 1024
ID = re.compile(r'J\d{4,6}')
LOCAL_ORIGIN = re.compile(r'http://(localhost|127\.0\.0\.1)(:\d{1,5})?')
LOCAL_HOST = re.compile(r'(localhost|127\.0\.0\.1)(:\d{1,5})?')


def origin_ok(origin):
    return origin is None or origin == 'null' or bool(LOCAL_ORIGIN.fullmatch(origin))


def validate(method, path, headers, body):
    """Pure (tested). headers = dict with lower-case keys; body = bytes. → (200, {id, pref}) or (code, {error})."""
    if not LOCAL_HOST.fullmatch(headers.get('host') or ''):
        return 421, {'error': 'bad host'}
    route = path.split('?')[0]
    if route not in ('/pref', '/action', '/apply', '/decline'):
        return 404, {'error': 'unknown path'}
    if method != 'POST':
        return 405, {'error': 'POST only'}
    if not origin_ok(headers.get('origin')):
        return 403, {'error': 'origin not allowed'}
    if headers.get('x-jsa-pref') != '1':
        return 403, {'error': 'missing X-JSA-Pref header'}
    if not (headers.get('content-type') or '').lower().startswith('application/json'):
        return 415, {'error': 'Content-Type must be application/json'}
    if len(body) > MAX_BODY:
        return 413, {'error': 'body too large'}
    try:
        d = json.loads(body.decode('utf-8'))
    except Exception:
        return 400, {'error': 'body is not JSON'}
    if route == '/apply':
        if not isinstance(d, dict) or set(d) != {'job_id', 'confirm'}:
            return 400, {'error': 'body must be a JSON object {job_id, confirm}'}
        if not isinstance(d['job_id'], str) or not ID.fullmatch(d['job_id']):
            return 400, {'error': 'bad job_id'}
        if d['confirm'] is not True:
            return 400, {'error': 'confirm must be true'}
        return 200, {'route': '/apply', 'job_id': d['job_id']}
    if route == '/decline':
        if not isinstance(d, dict) or set(d) != {'job_id', 'give_up'}:
            return 400, {'error': 'body must be a JSON object {job_id, give_up}'}
        if not isinstance(d['job_id'], str) or not ID.fullmatch(d['job_id']):
            return 400, {'error': 'bad job_id'}
        if not isinstance(d['give_up'], bool):
            return 400, {'error': 'give_up must be true or false'}
        return 200, {'route': '/decline', 'job_id': d['job_id'], 'give_up': d['give_up']}
    if route == '/action':
        if not isinstance(d, dict) or set(d) != {'job_id', 'done'}:
            return 400, {'error': 'body must be a JSON object {job_id, done}'}
        if not isinstance(d['job_id'], str) or not ID.fullmatch(d['job_id']):
            return 400, {'error': 'bad job_id'}
        if not isinstance(d['done'], bool):
            return 400, {'error': 'done must be true or false'}
        return 200, {'route': '/action', 'job_id': d['job_id'], 'done': d['done']}
    if not isinstance(d, dict) or set(d) != {'id', 'pref'}:
        return 400, {'error': 'body must be a JSON object {id, pref}'}
    if not isinstance(d['id'], str) or not ID.fullmatch(d['id']):
        return 400, {'error': 'bad id'}
    if d['pref'] not in ('up', 'down', 'clear'):
        return 400, {'error': 'pref must be up, down or clear'}
    return 200, {'id': d['id'], 'pref': d['pref']}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        origin = self.headers.get('Origin')
        if origin is not None and origin_ok(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def log_message(self, fmt, *a):
        sys.stderr.write('pref_server: ' + (fmt % a) + '\n')

    def _headers(self):
        return {k.lower(): v for k, v in self.headers.items()}

    def do_OPTIONS(self):                         # CORS preflight: only for local pages, only for /pref
        h = self._headers()
        if not LOCAL_HOST.fullmatch(h.get('host') or '') or self.path.split('?')[0] not in ('/pref', '/action', '/apply', '/decline') or not origin_ok(h.get('origin')):
            return self._send(403, {'error': 'preflight refused'})
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', h.get('origin') or 'null')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-JSA-Pref')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', '0'); self.end_headers()

    def do_GET(self):
        if self.path.split('?')[0] == '/health' and LOCAL_HOST.fullmatch(self.headers.get('Host') or ''):
            return self._send(200, {'ok': True})
        code, out = validate('GET', self.path, self._headers(), b'')
        return self._send(code, out)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(min(n, MAX_BODY + 1)) if n > 0 else b''
        code, req = validate('POST', self.path, self._headers(), body)
        if code != 200:
            return self._send(code, req)
        if req.get('route') == '/apply':
            sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'store'))
            import apply_req
            try:
                row = apply_req.queue(req['job_id'])
            except KeyError:
                return self._send(404, {'error': f"unknown job_id {req['job_id']}"})
            except ValueError as e:
                return self._send(409, {'error': str(e)[:300]})
            except Exception as e:
                return self._send(500, {'error': f'{type(e).__name__}: {e}'[:300]})
            desk = apply_req.ensure_desk()                # JSA-182: one desk; none listening → push Joey (never two runners)
            sys.stderr.write(f"pref_server: apply queued {row['id']} {row.get('company', '')} (desk {desk})\n")
            return self._send(200, {'job_id': row['id'], 'apply_req': row['apply_req'], 'apply_req_at': row['apply_req_at'], 'desk': desk})
        if req.get('route') == '/decline':   # JSA-406: Give up on the Waiting-for-you table (same write path as Done)
            sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'store'))
            import action_done
            try:
                row = action_done.apply_decline(req['job_id'], req['give_up'])
            except KeyError:
                return self._send(404, {'error': f"unknown job_id {req['job_id']}"})
            except ValueError as e:
                return self._send(409, {'error': str(e)[:300]})
            except Exception as e:
                return self._send(500, {'error': f'{type(e).__name__}: {e}'[:300]})
            sys.stderr.write(f"pref_server: {'give up' if req['give_up'] else 'undo give up'} {row['job_id']} {row.get('company', '')}\n")
            return self._send(200, {k: row.get(k) for k in ('job_id', 'status', 'action_needed', 'action_deadline', 'next_step', 'declined')})
        if req.get('route') == '/action':
            sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'store'))
            import action_done
            try:
                row = action_done.apply(req['job_id'], req['done'])
            except KeyError:
                return self._send(404, {'error': f"unknown job_id {req['job_id']}"})
            except ValueError as e:
                return self._send(409, {'error': str(e)[:300]})
            except Exception as e:
                return self._send(500, {'error': f'{type(e).__name__}: {e}'[:300]})
            sys.stderr.write(f"pref_server: action {'done' if req['done'] else 'undo'} {row['job_id']} {row.get('company', '')}\n")
            return self._send(200, {k: row.get(k) for k in ('job_id', 'action_needed', 'action_done')})
        import pref
        try:
            res = pref.apply([req['id']], req['pref'], via='dashboard')[0]
        except KeyError:
            return self._send(404, {'error': f"unknown id {req['id']}"})
        except Exception as e:                    # store.save refused (ValueError) or I/O: tell the page, write nothing
            return self._send(500, {'error': f'{type(e).__name__}: {e}'[:300]})
        sys.stderr.write(f"pref_server: {res['id']} {res['pref']} → {res['v_level']} · {res['score']} · {res['tier']}\n")
        return self._send(200, res)


if __name__ == '__main__':
    print(f'pref_server: http://127.0.0.1:{PORT}/pref — Ctrl-C to stop')
    HTTPServer(('127.0.0.1', PORT), H).serve_forever()
