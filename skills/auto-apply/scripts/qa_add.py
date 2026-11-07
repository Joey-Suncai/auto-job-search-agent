#!/usr/bin/env python3
"""Save the user's answer to a form question the rules did not know (JSA-164, Joey 2026-11-05) — the using-session way:
no code change, no new test. The answer goes into config/profile.json → qa; answer_rules.js reads it for every later form
that asks the same question (only where no rule answers it).

    python3 qa_add.py --q "Do you have a valid driver's license?" --no --source "Joey 2026-11-05 (Acme form)"
    python3 qa_add.py --q "Preferred shift" --pick "Day shift" --source "…"          # a list: the option to choose
    python3 qa_add.py --q "Years of Python experience" --text "3" --source "…"       # a text box
    python3 qa_add.py --q "…" --match "/driver'?s licen[cs]e/i" --yes --source "…"  # also other wordings (regex)
    python3 qa_add.py --list                                                          # what the table holds

Run it from the checkout the runners use (the main folder), so the live runners see the answer. It writes the profile,
rebuilds cx_bundle.js (the browser bundle embeds the profile), checks that answer_rules now answers the question, adds a
dated line to skills/_shared/decisions-log.md (when that file exists) and commits those files (--no-commit to skip).
Turning a frequent entry into a real rule (answer_rules.js + DeepSeek cases) is development work (CONTRIBUTING.md).
"""
import argparse, json, os, re, subprocess, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))


def norm(s):
    """Pure (tested). The same normalisation answer_rules.js uses for qa questions."""
    s = str(s or '').lower().replace('‘', "'").replace('’', "'")
    s = re.sub(r'\(?\brequired\b\)?|\*', ' ', s)
    return re.sub(r"[^a-z0-9']+", ' ', s).strip()


def entry(q, text=None, yes=None, pick=None, match=None, source='', today=None):
    """Pure (tested). The qa entry for one answer; ValueError when it holds no answer or more than one kind."""
    if not norm(q) and not match:
        raise ValueError('the question is empty')
    kinds = [k for k, v in (('text', text), ('yes', yes), ('pick', pick)) if v not in (None, '', [])]
    if len(kinds) != 1:
        raise ValueError('give exactly one answer: --text, --yes / --no, or --pick')
    if match and not re.fullmatch(r'/.+/[a-z]*', match):
        raise ValueError('--match must look like /regex/i')
    e = {'q': q.strip()}
    if match:
        e['match'] = match
    if text not in (None, ''):
        e['text'] = text
    if yes is not None:
        e['yes'] = bool(yes)
    if pick:
        rx = lambda p: re.fullmatch(r'/.+/[a-z]*', p.strip())        # a pick already written as /regex/i (a pattern principle, JSA-237)
        e['pick'] = [p.strip() if rx(p) else '/^' + re.escape(p.strip()) + '$/i' for p in pick]
        e['text'] = next((p.strip() for p in pick if not rx(p)), re.sub(r'^/|/[a-z]*$', '', pick[0].strip()))
    e['source'] = source or 'user'
    e['added'] = today or date.today().isoformat()
    return e


def add(profile, e, replace=False):
    """Pure (tested). Profile dict + entry → (profile, 'added' | 'replaced'); ValueError on a duplicate without replace."""
    qa = profile.setdefault('qa', [])
    i = next((k for k, x in enumerate(qa) if norm(x.get('q')) == norm(e['q'])), None)
    if i is not None:
        if not replace:
            raise ValueError(f'already in the table (#{i + 1}): {qa[i].get("q")!r} — use --replace')
        qa[i] = e
        return profile, 'replaced'
    qa.append(e)
    return profile, 'added'


def check(q, options, profile_path):
    """Ask answer_rules.js (through rules_bridge.js) for the question → its answer dict."""
    fields = [{'key': 'x', 'label': q, 'type': 'select' if options else 'text', 'options': options or []}]
    env = dict(os.environ, JSA_PROFILE=profile_path)
    r = subprocess.run(['node', os.path.join(HERE, '..', 'runner', 'rules_bridge.js'), os.path.join(HERE, 'answer_rules.js')],
                       input=json.dumps({'fields': fields, 'jd': '', 'company': ''}), capture_output=True, text=True, env=env, timeout=60)
    return (json.loads(r.stdout or '{}') or {}).get('x') or {}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--q', help='the question exactly as the form wrote it')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--text'); g.add_argument('--yes', action='store_true'); g.add_argument('--no', action='store_true')
    g.add_argument('--pick', action='append', help='the option to choose (repeat for fallbacks)')
    ap.add_argument('--match', help='also match other wordings: /regex/i')
    ap.add_argument('--options', help='the options the form showed, "|"-separated (for the check)')
    ap.add_argument('--source', default='', help='who answered and where, e.g. "Joey 2026-11-05 (Acme form)"')
    ap.add_argument('--replace', action='store_true'); ap.add_argument('--no-commit', action='store_true')
    ap.add_argument('--list', action='store_true')
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import paths as jp0
    ap.add_argument('--profile', default=os.environ.get('JSA_PROFILE') or jp0.config('profile.json'))   # the data home's profile (ADR-0008)
    a = ap.parse_args()
    prof = json.load(open(a.profile, encoding='utf-8'))
    if a.list:
        for n, e in enumerate(prof.get('qa') or [], 1):
            ans = e.get('text') if 'text' in e else ('Yes' if e.get('yes') else 'No')
            print(f"{n:3}. {e.get('q')!r} → {ans!r}  ({e.get('source')}, {e.get('added')})")
        return 0
    if not a.q:
        ap.error('--q is required')
    yes = True if a.yes else (False if a.no else None)
    try:
        e = entry(a.q, a.text, yes, a.pick, a.match, a.source)
        prof, how = add(prof, e, a.replace)
    except ValueError as ex:
        print('qa_add:', ex); return 1
    raw = open(a.profile, encoding='utf-8').read()
    indent = 1 if raw.startswith('{\n "') else 2
    open(a.profile, 'w', encoding='utf-8').write(json.dumps(prof, ensure_ascii=False, indent=indent) + '\n')
    opts = [o.strip() for o in a.options.split('|')] if a.options else []
    got = check(a.q, opts, a.profile)
    if got.get('status') != 'ok':                                 # never leave an entry that does not work: put the file back
        open(a.profile, 'w', encoding='utf-8').write(raw)
        if got.get('ask') and got.get('rule') in ('referral', 'know_employee', 'how_heard'):   # JSA-195: decided per company by the referrer pool
            print("qa_add: NOT saved — referral questions are answered per company from the referrer pool (config/connections.json): "
                  "not in the pool = no referral, in the pool = the user is asked; the qa table cannot answer them"); return 1
        print(f"qa_add: NOT saved — answer_rules still does not answer it with this entry: {got}"); return 1
    if not str(got.get('rule', '')).startswith('qa:'):
        print(f"qa_add: note — a rule already answers this question ({got.get('rule')} → {got.get('value')!r}); the table entry is only a fallback")
    print(f"qa_add: {how} → answer_rules: {got.get('value')!r} ({got.get('rule')})")
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import paths as jp                                           # the data home (ADR-0008)
    if os.path.abspath(a.profile) == os.path.abspath(jp.config('profile.json')):
        subprocess.run([sys.executable, os.path.join(HERE, 'build_bundle.py')], check=True)
        replay_after(e, HERE)                                    # JSA-188: what this answer changes on earlier forms
        home = jp.home()
        main = os.path.dirname(subprocess.run(['git', '-C', ROOT, 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                              capture_output=True, text=True).stdout.strip()) or ROOT   # the main checkout (docs live there)
        commits = {home: [os.path.relpath(a.profile, home), os.path.relpath(jp.bundle(), home)]}
        log = os.path.join(main, 'skills', '_shared', 'decisions-log.md')
        if os.path.exists(log):
            ans = e.get('text') if 'text' in e else ('Yes' if e.get('yes') else 'No')
            body = open(log, encoding='utf-8').read().rstrip('\n')
            open(log, 'w', encoding='utf-8').write(body + f"\n- {e['added']} — {e['source']}: {e['q']!r} → **{ans}** (config/profile.json qa, qa_add.py)\n")
            commits.setdefault(main, []).append(os.path.relpath(log, main))
        if not a.no_commit:
            msg = f"qa: {e['q'][:60]} → {str(e.get('text', e.get('yes')))[:30]} ({e['source'][:40]})"
            for repo, files in commits.items():                  # one repo when the data home is still this repo
                subprocess.run(['git', '-C', repo, 'add', '--'] + files, check=True)
                r = subprocess.run(['git', '-C', repo, 'commit', '-q', '-m', msg, '--'] + files, capture_output=True, text=True)
                print(f'qa_add: committed in {repo}' if r.returncode == 0 else f'qa_add: not committed in {repo} — ' + (r.stdout + r.stderr).strip()[:300])
    return 0


def replay_after(e, here):
    """JSA-188: re-answer every stored form with the new entry; answers it changes on SUBMITTED forms get this answer as
    their reason (it is Joey's own fact), and every change is printed so the session can tell him. Never fails qa_add."""
    rp = os.path.join(here, '..', '..', '..', 'scripts', 'learn', 'replay.py')
    if not os.path.exists(rp):
        return
    try:
        r = subprocess.run([sys.executable, rp, '--reason', f"qa_add {e.get('added', '')}: {e.get('source', '')} — {e.get('q', '')[:80]}"],
                           capture_output=True, text=True, timeout=300)
        out = [l for l in (r.stdout or '').splitlines() if l.strip()]
        print('qa_add: replay — ' + ('; '.join(out[:3]) if out else (r.stderr or 'no output').strip()[:200]))
        for l in out:
            if l.startswith('- '):
                print('  ' + l[:220])
    except Exception as ex:                                       # the answer is saved either way
        print(f'qa_add: replay skipped ({type(ex).__name__})')


if __name__ == '__main__':
    sys.exit(main())
