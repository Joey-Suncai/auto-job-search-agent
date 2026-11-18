#!/usr/bin/env python3
"""Form-prefetch questions waiting for Joey (JSA-243; the sheet is JSA-237).

The 09:15 routine (com.jobagent.prefetch → skills/auto-apply/runner/form_prefetch.py) writes the morning sheet
data/forms/questions.json but has no model: someone has to ask Joey. Until 2026-11-07 nothing told a session to — a day
with no using session opened (or one opened before 09:15) left the sheet unasked. This script is that signal.

    python3 scripts/store/prefetch_due.py                    # one line: how many questions wait on today's sheet (or none)
    python3 scripts/store/prefetch_due.py --json             # the same as JSON (ids, gain) for a session
    python3 scripts/store/prefetch_due.py --watch            # block until a NEW sheet has questions waiting, print, exit 0
    python3 scripts/store/prefetch_due.py --done [--how answered|deferred] [--n N]   # this sheet is handled

A question is "handled" once data/forms/asked.jsonl has a line for its sheet that lists it: collect_batch.py --apply on a
prefetch sheet writes the line itself (how = answered, every question of the sheet it applied); `--done --how deferred` is
for a day Joey says 「今天不答」. A sheet rebuilt the same day (`--sheet-only` after answering) keeps its name, but its new
questions still wait (JSA-244); tomorrow's sheet asks again — questions left unanswered come back on it.
The using session's SessionStart hook (scripts/ops_session.py, ADR-0011) prints the line; a using session asks right away, a developing session
only says that a using session should. `--watch` is for a long-running using session (next to done_since / apply_req).
Reads only, except --done (one appended line). Tests (rule 13): scripts/test_prefetch_due.py.
"""
import datetime as dt, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)

POLL = 60


def forms_dir():
    return os.environ.get('JSA_FORMS_DIR') or jpaths.data('forms')


def answer_of(sheet, q):
    """Pure (tested). The answer that collect_batch --apply would use for one entry: its own `answer`; else, when the sheet
    has accept_derived true, the `suggested` slot of an entry in the derived block that is not high-risk; else None."""
    if q.get('answer'):
        return None if isinstance(q['answer'], dict) and q['answer'].get('draft') else q['answer']   # JSA-366: a draft slot is no answer
    if sheet.get('accept_derived') and q.get('block') == 'derived' and not q.get('risk') and q.get('kind') != 'high_risk':
        return q.get('suggested') or None
    return None


def pending(sheet, handled):
    """Pure (tested). Ids of the sheet's questions still waiting for Joey, in sheet order. Nothing waits when the sheet is
    missing / not a dict or has no name. `handled`: a list / set of handled sheet names (the whole sheet is handled), or a
    dict {sheet name: set of question texts handled, or None = the whole sheet} (JSA-244: a sheet rebuilt the same day
    after --apply keeps its name but brings new questions — those still wait)."""
    if not isinstance(sheet, dict) or not sheet.get('name'):
        return []
    name = sheet['name']
    if not isinstance(handled, dict):
        if name in set(handled or ()):
            return []
        done = set()
    elif name in handled:
        if handled[name] is None:
            return []
        done = set(handled[name])
    else:
        done = set()
    return [q.get('id') for q in sheet.get('questions') or []
            if isinstance(q, dict) and answer_of(sheet, q) is None and q.get('question') not in done]


def gain(sheet):
    """Pure (tested). (ready now, ready after answering the whole sheet, jobs) from the sheet's summary; missing → 0."""
    s = (sheet or {}).get('summary') or {}
    return int(s.get('ready_now') or 0), int(s.get('ready_after') or 0), int(s.get('jobs') or 0)


def line(sheet, ids):
    """Pure (tested). The one-line status a session prints."""
    if not ids:
        name = (sheet or {}).get('name') if isinstance(sheet, dict) else None
        return f'prefetch questions: none waiting ({name or "no sheet"})'
    now, after, jobs = gain(sheet)
    return (f"prefetch questions: {len(ids)} waiting on {sheet['name']} — answering them makes {max(after - now, 0)} more "
            f"of {jobs} prefetched jobs ready ({now} ready now). Ask Joey in the chat (docs/agent/using.md → Morning).")


def load_sheet(d=None):
    try:
        return json.load(open(os.path.join(d or forms_dir(), 'questions.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return None


def load_handled(d=None):
    """asked.jsonl → {sheet name: set of question texts handled, or None (a line without "questions" = the whole sheet)}."""
    out = {}
    try:
        for l in open(os.path.join(d or forms_dir(), 'asked.jsonl'), encoding='utf-8'):
            try:
                x = json.loads(l)
                name, qs = x['sheet'], x.get('questions')
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            if qs is None or out.get(name, set()) is None:
                out[name] = None
            else:
                out[name] = out.get(name, set()) | {str(q) for q in qs}
    except OSError:
        pass
    return out


def mark(name, how='answered', n=None, d=None, questions=None):
    """Append one handled line for sheet `name` (asked.jsonl in the forms folder); questions = the texts handled
    (None = the whole sheet)."""
    d = d or forms_dir()
    os.makedirs(d, exist_ok=True)
    rec = {'sheet': name, 'how': how, 'n': n, 'at': dt.datetime.now().isoformat(timespec='seconds')}
    if questions is not None:
        rec['questions'] = [str(q) for q in questions]
    with open(os.path.join(d, 'asked.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def status(d=None):
    sheet = load_sheet(d)
    return sheet, pending(sheet, load_handled(d))


def main(a):
    if '--done' in a:
        sheet = load_sheet()
        if not sheet or not sheet.get('name'):
            print('prefetch_due: no sheet to mark'); return 1
        how = a[a.index('--how') + 1] if '--how' in a else 'answered'
        n = int(a[a.index('--n') + 1]) if '--n' in a else None
        qs = [q.get('question') for q in sheet.get('questions') or [] if isinstance(q, dict)]
        print('marked', json.dumps(mark(sheet['name'], how, n, questions=qs), ensure_ascii=False)[:300]); return 0
    if '--watch' in a:
        _, before = status()
        before = set(before)
        while True:
            time.sleep(POLL)
            sheet, ids = status()
            if set(ids) - before:                      # questions waiting that were not waiting when the watch started
                print(line(sheet, ids)); return 0
            before = set(ids)                          # answered / handled ones drop out, so a later new one still wakes
    sheet, ids = status()
    if '--json' in a:
        now, after, jobs = gain(sheet)
        print(json.dumps({'sheet': (sheet or {}).get('name'), 'waiting': ids, 'ready_now': now, 'ready_after': after, 'jobs': jobs}))
    else:
        print(line(sheet, ids))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
