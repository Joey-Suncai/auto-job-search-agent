#!/usr/bin/env python3
"""The three segments every platform runner shares (JSA-187, docs/specs/runner-apply-self-optimization.md).

Only these three — page work (sign-in, paging, widgets, uploads, pressing the button) stays in the platform runner:
  1. opening checks   already submitted · batch approved · materials gate + the folder's tailored resume (presubmit.before)
  2. submit gate      canon on the irreversible fields · every field read back · zero unknown questions · approved
  3. closing books    confirmation screenshot · one results line (per-phase seconds, stopped_at) · fields.jsonl ·
                      sync_results · close the posting's tabs · queue / push what needs Joey

Rule (risk 3 in the spec): **no platform name in this file.** A platform difference comes in as a parameter (`ats`, the
label used in a push, extra tab URLs, `wait_after_submit`), the decision stays in the platform runner.

Every stop names its layer (risk 4): `stopped_at` = "common_gate" (a check in this file stopped it: materials, canon,
approval, read-back, unknown) or "platform_page" (the runner's own page work stopped: sign-in, CAPTCHA, a refused
button, a runner error). The log line reads 「停在：公共关卡」 / 「停在：平台页面」.

    import runner_common as RC
    R = RC.Run(ats, posting, folder, out, submit=a.submit, log=log)        # opening: phase 'open'
    if R.already_submitted(): return
    if not R.opening(resume): return                                      # submit + materials problem: stopped, recorded
    R.mark('page'); r = run(page, …)                                      # platform page work
    decision = R.gate(r)                                                  # 'press' | 'dry-run' | 'blocked'
    if decision == 'press': R.mark('submit'); r['status'], cb = submit(…)  # platform presses the button
    R.finish(r, ctx=ctx, page=page, confirmed_by=cb)                      # closing books
"""
import json, os, re, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
import run_form as RF      # noqa: E402  queue / push / approved_for / already_submitted / close_posting_tabs (shared helpers)
import presubmit as PS     # noqa: E402  materials gate + tailored resume + canon audit (JSA-186)
import canon               # noqa: E402


def start_shadow(data_dir):
    """JSA-361 shadow run (Joey 2026-11-16): the question-type layer reads the fields this run just wrote, beside the live
    rules, in a detached process (scripts/learn/qtype_shadow.py). It changes no answer; anything that goes wrong here is
    swallowed — a run is never stopped or slowed by it. Off in tests and with CX_QTYPE_SHADOW=0."""
    try:
        learn = os.path.join(ROOT, 'scripts', 'learn')
        if learn not in sys.path:
            sys.path.insert(0, learn)
        import qtype_shadow
        return qtype_shadow.start_shadow(data_dir)
    except Exception:
        return False

COMMON, PAGE = 'common_gate', 'platform_page'
LAYER_ZH = {COMMON: '停在：公共关卡', PAGE: '停在：平台页面'}
DONE = ('submitted', 'dry-run')


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


# ----------------------------------------------------------------------------- pure helpers (tested)
def field_rows(result):
    """Pure. Every read-back field of a runner result (top-level `fields`, `sections[].fields`, `steps[].fields`) in one
    shape: {question, planned, page, source, type, required, ok, options}."""
    rows = []
    for f in PS.fields_of(result or {}):
        rows.append({'question': str(f.get('label') or f.get('key') or '')[:4000],   # the whole question (JSA-288: a 300 cut lost the asking sentence after a long notice)
                     'planned': f.get('want') if 'want' in f else f.get('answer'),
                     'page': f.get('page') if 'page' in f else f.get('value'),
                     'source': f.get('source') or f.get('rule') or f.get('why') or '',
                     'type': f.get('type') or f.get('kind') or '',
                     'required': bool(f.get('required')),
                     'ok': f.get('ok') if 'ok' in f else (f.get('status') in ('ok', 'keep', 'skip') if f.get('status') else None),
                     'options': list(f.get('options') or [])[:40]})
    return rows


def block_problems(result, folder=None, log=None):
    """JSA-294: every education / work block box the page holds, judged by code against the entry of its block
    (block_check.py: "Education (UIUC): Degree" label prefixes, sections, the runner's entry). A failing check is a
    problem too: a block that cannot be checked is not submitted."""
    try:
        import block_check as BC
        out = ['block check: ' + p for p in BC.problems(PS.fields_of(result or {}), overrides=BC.load_overrides(folder))]
    except Exception as e:
        out = [f'block check failed: {type(e).__name__}: {str(e)[:100]}']
    for p in out:
        (log or (lambda m: None))(p)
    return out


def readback_bad(rows):
    """Pure. Questions whose read-back is not confirmed (ok is not True)."""
    return [r['question'] for r in rows if r.get('ok') is not True]


def stopped_layer(platform_problems, common_problems, status):
    """Pure. Which layer stopped the run: None when it went through (submitted / clean dry run), PAGE when the platform
    runner reported a problem or a non-final status of its own, else COMMON."""
    if status in DONE and not platform_problems and not common_problems:
        return None
    if platform_problems:
        return PAGE
    if common_problems:
        return COMMON
    return None if status in DONE else PAGE


def _commit_result(path, line):
    """JSA-358: the runner commits its own results.jsonl line on the spot (best effort; never fails a run)."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'scripts', 'store'))
        import data_git
        data_git.commit_paths([path], f"data: runner {line.get('status')} — {line.get('folder')}")
        if line.get('folder'):                             # JSA-412: and the application folder's files this run wrote (run_log, form_check, plan, application_record …)
            data_git.commit_application(line['folder'], f"data: application {line.get('status')} — {line.get('folder')}")
    except Exception:  # noqa: BLE001
        pass


def results_line(*, at, folder, url, ats, status, mode, problems, fields, bad, secs, phases, stopped_at, tenant,
                 confirmed_by=None, by='runner', extra=None):
    """Pure. The one results.jsonl shape for every runner — the old keys unchanged (sync_results, platform_scorecard,
    already_submitted read them) plus phases / stopped_at / tenant."""
    d = {'at': at, 'folder': folder, 'url': url, 'ats': ats, 'status': status, 'mode': mode,
         'problems': list(problems or [])[:8], 'fields': fields, 'bad': bad, 'secs': secs, 'by': by,
         'phases': phases, 'stopped_at': stopped_at, 'tenant': tenant}
    if confirmed_by:
        d['confirmed_by'] = confirmed_by
    for k, v in (extra or {}).items():
        d.setdefault(k, v)
    return d


def field_lines(rows, *, run_id, at, folder, ats, tenant, hard):
    """Pure. One fields.jsonl line per field; `canon` = 'mismatch' when the audit blocked it, the canonical key when the
    question is a high-stakes one that passed, else ''."""
    bad_labels = {str(h.get('label') or '')[:120] for h in hard or []}
    out = []
    for r in rows:
        key = canon.classify(canon.question_of(r['question'])) or ''
        c = 'mismatch' if r['question'][:120] in bad_labels else key
        out.append({'run_id': run_id, 'at': at, 'folder': folder, 'ats': ats, 'tenant': tenant, **r, 'canon': c})
    return out


# ----------------------------------------------------------------------------- the run
def unconfirmed_action(r):
    """Pure (tested, JSA-391). 'pending' for an `unconfirmed` result flagged receipt_pending (the receipt e-mail is checked
    later by receipt_confirm: log only), else 'joey' (queue line + push)."""
    return 'pending' if (r or {}).get('receipt_pending') is True else 'joey'


class Run:
    """One application run. `submit` = the runner will press the final button when every gate passes (the platform runner
    decides what it passes here: --submit, or --submit AND approved); `label` names the platform in pushes to Joey."""

    def __init__(self, ats, posting, folder, out, submit, log=None, label=None, data_dir=None):
        self.ats, self.posting, self.folder, self.out = ats, posting, folder, out
        self.submit = bool(submit)
        self.mode = 'submit' if self.submit else 'dry-run'
        self.label = label or ats
        self.data = data_dir or RF.DATA
        self.log = log or print
        self.t0 = time.time()
        self.phases, self._cur, self._since = {}, None, None
        self.pre, self.common, self.queued, self.stopped_at = [], [], False, None
        self.tenant = canon.tenant_of(posting)
        self.mark('open')

    # timing
    def mark(self, name):
        """Close the current phase, start `name` (open · page · submit · confirm · close, or the runner's own names)."""
        t = time.time()
        if self._cur:
            self.phases[self._cur] = round(self.phases.get(self._cur, 0) + t - self._since, 1)
        self._cur, self._since = name, t

    def secs(self):
        return round(time.time() - self.t0, 1)

    def _q(self, msg):
        if self.folder and not self.queued:
            RF.queue(self.folder, msg, self.posting); self.queued = True

    # 1. opening checks
    def already_submitted(self):
        if self.folder and RF.already_submitted(self.folder):
            print(f'{os.path.basename(self.folder)}: already submitted — nothing to do'); print('STATUS already-submitted')
            return True
        return False

    def approved(self):
        return bool(self.folder and RF.approved_for(self.folder))

    def opening(self, resume):
        """Materials gate + tailored resume (only with a folder). False = a submit run stopped here: blocked line written,
        queued, STATUS printed — the runner returns without opening the form. In a dry run problems are only kept."""
        import chrome_lock                                    # JSA-236: one driver of the job Chrome at a time
        chrome_lock.hold(f"{self.ats} {os.path.basename(self.folder or self.posting or '')}", log=self.log)
        import chrome_guard                                   # JSA-227: no autofill / password extension in the job Chrome (dry runs too)
        guard = chrome_guard.problems()
        if guard:
            self.common += guard; self.stopped_at = COMMON
            self.log('NOT started: ' + ' | '.join(guard))
            self._q(guard[0][:300])
            self._write({'status': 'blocked', 'problems': guard, 'unknown': []}, rows=[], hard=[])
            self.log(f'STATUS blocked · {LAYER_ZH[COMMON]} TIME {self.secs()}s')
            return False
        self.pre = PS.before(self.folder, resume, self.ats, self.log) if self.folder else []
        if self.pre and self.submit:
            self.common += self.pre
            self.stopped_at = COMMON
            self.log('NOT submitted (before filling): ' + ' | '.join(self.pre))
            self._q('not submitted: ' + ' | '.join(self.pre)[:300])
            self._write({'status': 'blocked', 'problems': self.pre, 'unknown': []}, rows=[], hard=[])
            self.log(f'STATUS blocked · {LAYER_ZH[COMMON]} TIME {self.secs()}s')
            return False
        return True

    # 2. submit gate
    def check(self, r):
        """canon audit + read-back + unknown on the result, in place. Returns the common-gate problems (may be [])."""
        hard, warn = PS.audit(r, self.posting, self.log)
        r['canon'], r['canon_warn'] = hard, warn
        rows = field_rows(r)
        probs = PS.lines(hard) + PS.review(r, self.log, self.folder or '')    # final_review: independent re-read of the key cells (JSA-355)
        bad = readback_bad(rows)
        if bad:
            probs.append('fields not confirmed on the page: ' + '; '.join(q[:40] for q in bad[:6]))
        if not rows:
            probs.append('no field was read back')
        probs += block_problems(r, self.folder, self.log)
        return probs

    def gate(self, r, checked=None):
        """May the platform runner press the final button? 'press' | 'dry-run' | 'blocked' (submit run stopped: queued).
        r['problems'] / r['unknown'] = what the platform runner found; this adds the common checks to r['problems'].
        `checked` = the result of an earlier self.check(r) (a runner that must know before asking Joey for a CAPTCHA)."""
        plat = list(r.get('problems') or []) + list(r.get('unknown') or [])
        own = r.get('status') or 'dry-run'                     # the page work's own end state; only 'dry-run' = ready
        if own != 'dry-run' and not plat:
            plat.append(f'the page work ended with status {own}')
        common = [p for p in self.pre if p not in plat] + [p for p in (self.check(r) if checked is None else checked) if p not in plat]
        if not plat and self.submit and not self.approved():
            common.append('batch not approved (data/runner/approved_batches.json)')
        self.common += common
        r['problems'] = list(r.get('problems') or []) + [p for p in common if p not in (r.get('problems') or [])]
        if plat or common:
            self.stopped_at = PAGE if plat else COMMON
            self.log('problems: ' + ' | '.join(plat + common) + (' — NOT submitted' if self.submit else ''))
            if self.submit:
                if own == 'dry-run':
                    r['status'] = 'blocked'                    # ready on the page, stopped by a check
                else:
                    r['status'] = own                          # captcha / needs-user / closed / blocked keep their name
                if r['status'] != 'closed':
                    self._q('not submitted: ' + ' | '.join(plat + common)[:300])
                return 'blocked'
            return 'dry-run'
        if not self.submit:
            self.log('every field read back — dry-run, NOT submitted')
            return 'dry-run'
        return 'press'

    def gate_inside(self, res):
        """For runners that press the final button inside their page loop: the canon audit + approval right before it.
        True = press. False = res is blocked (problems added; the runner returns res)."""
        hard, warn = PS.audit(res, self.posting, self.log)
        res['canon'], res['canon_warn'] = hard, warn
        probs = PS.lines(hard) + PS.review(res, self.log, self.folder or '')    # final_review (JSA-355)
        if not self.approved():
            probs.append('batch not approved (data/runner/approved_batches.json)')
        if probs:
            self.common += probs; self.stopped_at = COMMON
            res['status'] = 'blocked'
            res['problems'] = list(res.get('problems') or []) + [p for p in probs if p not in (res.get('problems') or [])]
            self.log('NOT pressed: ' + ' | '.join(probs))
            return False
        return True

    def report(self, r):
        """For runners whose page loop already decided (pressed, or stopped before the button): add the common checks to
        r['problems'] for the record without changing r['status'] (a dry run shows what a submit would have hit)."""
        if 'canon' in r and r.get('status') in ('submitted', 'unconfirmed'):
            return []
        plat = list(r.get('problems') or []) + list(r.get('unknown') or [])
        common = [p for p in self.pre + self.check(r) if p not in plat]
        if self.submit and r.get('status') not in ('submitted', 'unconfirmed') and not self.approved():
            common.append('batch not approved (data/runner/approved_batches.json)')   # --submit without approval: filled, never pressed
            if r.get('status') == 'dry-run':
                r['status'] = 'blocked'
        self.common += common
        r['problems'] = list(r.get('problems') or []) + [p for p in common if p not in plat]
        if self.stopped_at is None and (plat or common or r.get('status') not in DONE + ('unconfirmed',)):
            self.stopped_at = PAGE if (plat or r.get('status') not in DONE + ('blocked', 'unconfirmed')) else COMMON
        return common

    # 3. closing books
    def _write(self, r, rows, hard, confirmed_by=None, extra=None):
        os.makedirs(self.data, exist_ok=True)
        at = now()
        if self._cur:
            self.mark(self._cur)                              # flush the running phase into self.phases
        line = results_line(at=at, folder=os.path.basename(self.out or self.folder or ''), url=self.posting, ats=self.ats,
                            status=r.get('status'), mode=self.mode,
                            problems=list(r.get('problems') or []) + list(r.get('unknown') or []),
                            fields=len(rows), bad=len(readback_bad(rows)), secs=self.secs(), phases=dict(self.phases),
                            stopped_at=self.stopped_at, tenant=self.tenant, confirmed_by=confirmed_by, extra=extra)
        with open(os.path.join(self.data, 'results.jsonl'), 'a') as o:
            o.write(json.dumps(line) + '\n')
        _commit_result(os.path.join(self.data, 'results.jsonl'), line)
        if rows:
            fdir = os.path.join(self.data, 'fields'); os.makedirs(fdir, exist_ok=True)
            run_id = f"{line['folder']}@{at}"
            with open(os.path.join(fdir, at[:7] + '.jsonl'), 'a') as o:
                for fl in field_lines(rows, run_id=run_id, at=at, folder=line['folder'], ats=self.ats, tenant=self.tenant, hard=hard):
                    o.write(json.dumps(fl, ensure_ascii=False) + '\n')
            start_shadow(self.data)
        return line

    def finish(self, r, ctx=None, page=None, confirmed_by=None, extra_urls=(), keep_tab=False, extra=None, told=False):
        """Results line + fields.jsonl, then: submitted → confirmation screenshot (if the runner did not), tracker row
        (sync_results), every tab of the posting closed; unconfirmed → queue + push; another non-final status of a submit
        run → queue (once). Never raises: the books of a pressed button must not be lost to a closing error."""
        self.mark('close')
        status = r.get('status')
        confirmed_by = confirmed_by or r.get('confirmed_by')
        if self.stopped_at is None and status not in DONE + ('unconfirmed',):
            self.stopped_at = PAGE
        rows = field_rows(r)
        if status == 'submitted' and page is not None and self.out:
            shot = os.path.join(self.out, 'submitted_confirmation.png')
            if not os.path.exists(shot):
                try:
                    import confirm_page as CP
                    CP.confirmation_shot(page, shot, self.log)   # JSA-223
                except Exception: pass
        line = self._write(r, rows, r.get('canon') or [], confirmed_by=confirmed_by, extra=extra)
        try:
            if status == 'submitted':
                sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
                import sync_results; sync_results.sync_folder(self.folder, self.log)
                closed = 0
                if ctx is not None:
                    closed = RF.close_posting_tabs(ctx, self.posting) + sum(RF.close_posting_tabs(ctx, u) for u in extra_urls if u)
                if page is not None and not page.is_closed():
                    page.close(); closed += 1
                self.log(f'closed {closed} tab(s) of this posting')
            elif told and status == 'unconfirmed':                 # the runner already queued / pushed this stop itself (JSA-196)
                pass
            elif status == 'unconfirmed' and unconfirmed_action(r) == 'pending':
                self.log('receipt pending — receipt_confirm checks Gmail later (48 h without a receipt → Joey)')
            elif status == 'unconfirmed':
                self._q('pressed the final button but no confirmation page and no company e-mail — check Gmail')
                RF.push('求职 runner：没有确认', os.path.basename(self.out or '')[11:60] + f' — {self.label} 页面和邮件都没确认，交给你')
            elif self.submit and status not in DONE + ('closed',):     # a closed posting is archived, not Joey's
                self._q(f'not submitted ({status}): ' + ' | '.join(list(r.get('problems') or []) + list(r.get('unknown') or []))[:300])
            import tab_policy                                 # Joey 2026-11-05: every finished run closes its tab (dry run included); only a CAPTCHA stays
            if status != 'submitted' and page is not None and not page.is_closed() and not tab_policy.keep_open(status, keep_tab):
                page.close(); self.log('closed this run\'s tab (' + str(status) + ')')
        except Exception as e:
            self.log(f'closing step error {type(e).__name__}: {str(e)[:160]} (results line already written)')
        where = f' · {LAYER_ZH[self.stopped_at]}' if self.stopped_at else ''
        ok = line['fields'] - line['bad']
        self.log(f"STATUS {status}{where} readback {ok}/{line['fields']} TIME {self.secs()}s")
        return line
