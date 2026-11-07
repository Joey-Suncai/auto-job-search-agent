#!/usr/bin/env python3
"""Build the public open-source tree from this private repo (JSA-078, ADR-0005). Nothing is pushed.

Takes the git-tracked files, keeps only what `keep()` allows (code, skills, templates, the fictional config/*.example
files), swaps in the public README / CLAUDE.md, then runs scan.py on the result: any personal value → exit 1.
usage: python3 scripts/public/export_public.py --out DIR [--git]      (DIR must not exist; --git = one fresh root commit, tag v0.1)
       python3 scripts/public/export_public.py --update CLONE --version v0.2
                 release 2+ (JSA-089): export into a temp tree, scan (0 hits), run its scripts/test_all.sh on a copy, then
                 replace CLONE's tracked files with the export (stale ones removed, .git and ignored files kept) and make one
                 normal commit + tag on top of the public history. Never pushes: prints the push command.
       python3 scripts/public/export_public.py --list                (print the kept files, write nothing)
Tests (rule 13): scripts/test_export_public.py and scripts/test_export_update.py with DeepSeek cases.
"""
import fnmatch, hashlib, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, HERE)
import scan  # noqa: E402

# whole areas that are personal data, application history or private working notes
DENY_DIRS = ('applications/', 'data/', 'resume/', '资料/', 'maps/', 'map/', 'github-profile/', 'phase2-prompts/', 'docs/',
             '.claude/', 'dashboard/', 'node_modules/', 'skills/job-search-agent/references/', 'skills/linkedin-updater/',
             'skills/github-profile-builder/', 'skills/resume-updater/references/', 'skills/auto-apply/references/',
             'skills/job-hunt-pipeline/references/', 'config/examples/')
DENY_FILES = ('BACKLOG.md', 'ROADMAP.md', 'ARCHITECTURE.md', 'PLAN-git-source-of-truth.md', 'CLAUDE.md', 'README.md',
              'github-avatar.png', 'skills/_shared/candidate-profile.md', 'skills/_shared/story-bank.md',
              'skills/_shared/bullet-bank.md', 'skills/_shared/decisions-log.md', 'skills/_shared/visa-and-sponsorship.md', 'skills/_shared/prompts.md',
              'skills/auto-apply/scripts/cx_bundle.js', 'scripts/daily/notify.json', 'skills/job-hunt-pipeline/daily-new-roles-prompt.md',
              # the author's own development workflow (Joey 2026-11-02: 「可以删掉」): backlog, worktree landing / sync, claude.ai shadow
              'scripts/backlog.py', 'scripts/test_backlog.py', 'scripts/test_backlog_layout.py',
              'scripts/session_mode.py', 'scripts/test_session_mode.py',   # the author's two-system switch: needs docs/agent + .claude (both private)
              # the author's two-system tools (release, use guard, path checks) stay private (Joey 2026-11-05 「不公开」)
              'scripts/release.py', 'scripts/test_release.py', 'scripts/use_guard.py', 'scripts/test_use_guard.py',
              'scripts/install_use_guard.py', 'scripts/test_install_use_guard.py', 'scripts/config_path_check.py',
              'scripts/test_config_paths.py', 'scripts/paths_literal.py', 'scripts/test_paths.py',
              'scripts/test_cases/session_mode_spec.md', 'scripts/test_cases/session_mode_format.md', 'scripts/test_cases/session_mode_cases.json',
              'scripts/test_cases/backlog_layout_spec.md', 'scripts/test_cases/backlog_layout_format.md',
              'scripts/test_cases/backlog_layout_cases.json', 'scripts/test_cases/backlog_layout_verdicts.json',
              'scripts/test_backlog_fix.py', 'scripts/test_cases/backlog_fix_spec.md', 'scripts/test_cases/backlog_fix_format.md',
              'scripts/test_cases/backlog_fix_cases.json', 'scripts/test_cases/backlog_fix_verdicts.json',   # JSA-214
              'scripts/land.py', 'scripts/sync_worktrees.py',
              'scripts/test_sync_worktrees.py', '.githooks/post-commit', '.githooks/post-merge', 'scripts/store/claude_export.py',
              'skills/daily-job-refresh/scripts/kit.py', 'skills/job-search-agent/SKILL.md',
              'scripts/test_export_companies.py')   # tests the export step itself, whose fixtures it would rewrite
# tests whose expected values ARE the candidate's EEO / citizenship / GPA answers: they run in the private repo only
PRIVATE_TESTS = ('scripts/test_answers_1101b.js', 'scripts/test_answers_1103b.js', 'scripts/test_bridge_date.py', 'scripts/test_gender_canon_label.py',
                 'scripts/test_language_blocks.py', 'scripts/test_long_eeo.js', 'scripts/test_race_hispanic.js',
                 'skills/auto-apply/runner/test/t_canon.py', 'skills/auto-apply/runner/test/t_wd_logic.py',
                 'skills/auto-apply/runner/test/t_facts.py', 'skills/auto-apply/scripts/test/t_answers.js',
                 'skills/auto-apply/scripts/test/t_jsdom.js', 'skills/auto-apply/scripts/test/t_rules.js',
                 # match senders / domains against tracker company names word by word: invented names cannot stand in (JSA-085)
                 'scripts/daily/test_email_check.py', 'scripts/test_choose_mail.py', 'scripts/test_choose_code.py',
                 # its spec and cases state the candidate's own GPA (JSA-085, 11-04)
                 'scripts/test_rules_batch1104.py',
                 # its spec and cases state the candidate's EEO / degree answers (JSA-092, 11-05)
                 'scripts/test_rules_sf1105.py',
                 # its spec and cases state the candidate's resume employers and sponsorship answers (JSA-092, 11-05 fourth round)
                 'scripts/test_rules_sf1105d.py',
                 # its spec, cases and real-form fixtures state the candidate's EEO / sponsorship answers (JSA-186, 11-05)
                 'scripts/test_presubmit.py',
                 # its spec states the candidate's visa / veteran / GPA facts (JSA-188, 11-05)
                 'scripts/test_replay_fixes_1105.py',
                 # their specs and cases state the candidate's GPA / EEO answers (JSA-202 / 203 / 205, 11-05 – 11-06)
                 'scripts/test_infer_facts.py', 'scripts/test_high_risk.py', 'scripts/test_answer_shape.js', 'scripts/test_qtype_route.py',
                 'scripts/test_rules_1105g.py', 'scripts/test_second_opinion.py')
PRIVATE_CASES = ('infer_facts_', 'high_risk_', 'answer_shape_', 'qtype_route_', 'rules_1105g_', 'second_opinion_', 'rules_batch1104_', 'rules_sf1105_', 'rules_sf1105d_', 'presubmit_', 'replay_fixes_1105_', 'answers_1101b_', 'answers_1103b_', 'gender_canon_label_', 'language_blocks_', 'long_eeo_', 'race_hispanic_', 'choose_mail_cases', 'choose_mail_spec',
                 'choose_mail_format', 'choose_mail_verdicts', 'choose_code_',
                 'backlog_', 'sync_worktrees_', 'export_companies_',
                 'release_', 'use_guard_', 'install_use_guard_', 'config_path_', 'paths_', 'session_mode_')   # the private two-system tools' cases
DENY_GLOBS = ('*_bak*', '*/_bak*/*', '*_archive*', '*.bak', '*_before_*', '*.pdf', '*.docx', '*.png', '*.jpg', '*.jpeg',
              '*.tgz', '*.zip', '*.xlsx', '*.jsonl')
# personal data files under config/: only their .example twins ship
CONFIG_PUBLIC = ('config/README.md', 'config/profile.js', 'config/connections.js', 'config/jsa_profile.py', 'config/paths.py')   # paths.py = the data home (ADR-0008): missing from the export 11-04 → 11-05
ALLOW = ('data/processed/perm_ellis.txt',   # public PERM sponsor list used by the refresh
         'skills/auto-apply/runner/test/app_fake/resume_fixture.pdf', 'skills/auto-apply/runner/test/app_bad/resume_fixture.pdf',
         'skills/auto-apply/runner/test/app_notready/resume_fixture.pdf',   # 60-byte dummy PDFs the runner tests upload
         'map/template.html')   # the live map's static page (map/index.html is built with live data and stays out)   # 60-byte dummy PDFs the runner tests upload
# public replacements: source in the repo → path in the export
# public brand data (who files H-1B under which name) and the tests that check it: company names stay as they are, since
# replacing them breaks the alias families and they say nothing about the user's applications (JSA-085, 2026-11-03)
PUBLIC_DATA = ('skills/job-hunt-pipeline/scripts/h1b_names.json', 'scripts/test_h1b_match.py')
PUBLIC_DATA_CASES = ('h1b_match_', 'h1b_names_')
# companies that are also a supported application platform (skills/ats-tiktok, run_tiktok.py) or a job board the code
# names (skills/auto-apply/runner/job_board.py BOARDS — "ZipRecruiter" is also a company the user applied to): never replaced
PLATFORM_NAMES = ('tiktok', 'bytedance', 'linkedin', 'indeed', 'glassdoor', 'ziprecruiter', 'monster', 'careerbuilder',
                  'handshake', 'wellfound', 'dice', 'built in', 'craigslist', 'simplify')
SWAP = {'docs/public/README.md': 'README.md', 'docs/public/CLAUDE.template.md': 'CLAUDE.md', 'docs/public/CONTRIBUTING.md': 'CONTRIBUTING.md',
        'docs/public/ci.yml': '.github/workflows/ci.yml'}


def pseudo_pairs(private, example, home=None):
    """Pure (tested). Private profile + fictional example → [(regex, replacement)], longest first: the candidate's identity
    (name, e-mails, phone in any format, street, handles, home folder) becomes the example person's in every exported text."""
    pv, ex = private or {}, example or {}
    g = lambda d, k: (d.get(k.split('.')[0]) or {}).get(k.split('.')[1]) if '.' in k else d.get(k)
    pairs = []
    for k in ('name.signature', 'name.full', 'name.file_prefix', 'contact.email', 'accounts.gmail', 'accounts.workday_email', 'name.first'):
        a, b = g(pv, k), g(ex, k) or ''
        if a and a != b:
            pairs.append((re.escape(a), b, len(a)))
    for k in ('contact.linkedin', 'contact.website'):
        a, b = (g(pv, k) or '').rstrip('/').split('/')[-1], (g(ex, k) or 'example').rstrip('/').split('/')[-1]
        if len(a) >= 4 and a != b:
            pairs.append((r'\b' + re.escape(a) + r'\b', b, len(a)))
    for e in {g(pv, 'contact.email'), g(pv, 'accounts.gmail')} - {None, ''}:
        u = e.split('@')[0]
        pairs.append((r'\b' + re.escape(u) + r'\b', (g(ex, 'contact.email') or 'you@example.com').split('@')[0], len(u)))
    ph, eph = re.sub(r'\D', '', g(pv, 'contact.phone') or '')[-10:], re.sub(r'\D', '', g(ex, 'contact.phone') or '5550102030')[-10:]
    if len(ph) == 10:
        pairs.append((r'(?<!\d)(\+?1[\s.-]?)?(\(?)' + ph[:3] + r'(\)?[\s.-]?)' + ph[3:6] + r'([\s.-]?)' + ph[6:] + r'(?!\d)',
                      r'\g<1>\g<2>' + eph[:3] + r'\g<3>' + eph[3:6] + r'\g<4>' + eph[6:], 20))
        pairs.append((r'(?<!\d)' + ph[3:] + r'(?!\d)', eph[3:], 7))
    z, ez = ((pv.get('answers') or {}).get('zip') or {}).get('text'), ((ex.get('answers') or {}).get('zip') or {}).get('text') or '00000'
    if z and z != ez:
        pairs.append((r'(?<!\d)' + re.escape(z) + r'(?!\d)', ez, len(z)))
    st = ((pv.get('answers') or {}).get('address') or {}).get('text')
    if st:
        pairs.append((re.escape(st), ((ex.get('answers') or {}).get('address') or {}).get('text') or '1 Example St', len(st)))
    if home:
        pairs.append((re.escape(home.rstrip('/')) + r'\b', '/Users/you', len(home)))
    return [(rx, b) for rx, b, _ in sorted(pairs, key=lambda x: -x[2])]


def pseudonymize(text, pairs):
    """Pure (tested). Apply pseudo_pairs() to one text."""
    for rx, b in pairs:
        text = re.sub(rx, b, text, flags=re.I)
    return text


# product / technical names that contain a company name and must stay (the code uses them)
PROTECT = re.compile(r'Microsoft Edge|Google Chrome|Intel Mac|Meta\+|Apple(?:WebKit|Script)|Amazon (?:Linux|Web Services|S3)|Adobe (?:PDF|Acrobat)')
DATED = r'(?=[\s,(\-–·]{0,3}(?:20\d\d-\d\d|\d{1,2}-\d{2}\b|J\d{5}))'   # "Box 2026-10-31", "Acme 10-28", "Acme J00001"
ATS_LABEL = (('myworkdayjobs', 'a Workday employer'), ('myworkdaysite', 'a Workday employer'), ('greenhouse', 'a Greenhouse employer'),
             ('lever.co', 'a Lever employer'), ('ashbyhq', 'an Ashby employer'))
DOCQ = ('"' * 3, "'" * 3)


def company_pairs(apps, jobs=None, words=()):
    """Pure (tested). Tracker rows (+ jobs by id for the posting URL) → [(regex, generic label, name)], longest name first
    (JSA-085, Joey 2026-11-02: 「公司名换成泛称」). A name that is also an English word ("Square", "Box", "Gap") is
    replaced in code comments only where it reads as a reference — followed by a date or a job id."""
    url_of = {j.get('id'): j.get('ats_url') or j.get('url') or '' for j in (jobs or [])}
    out = {}
    for a in apps or []:
        c = (a.get('company') or '').strip()
        if len(c) < 3 or c.lower() in PLATFORM_NAMES:
            continue
        u = (a.get('url') or url_of.get(a.get('job_id')) or '').lower()
        out.setdefault(c, next((l for k, l in ATS_LABEL if k in u), 'an employer'))
    pairs = []
    for c in sorted(out, key=len, reverse=True):
        rx = r'(?<![\w&.-])' + re.escape(c) + r'(?![\w&-])'
        if c.lower() in words:
            rx += DATED
        pairs.append((rx, out[c], c))
    return pairs


SYL = ('bra', 'cor', 'del', 'fen', 'gal', 'har', 'kel', 'lum', 'mor', 'nev', 'ost', 'pell', 'quin', 'ros', 'sev', 'tal', 'ver', 'wyn')


def fictional_name(name, taken=()):
    """Pure (tested). A stable invented company name for `name` (same input → same output) that is not in `taken`."""
    h = int(hashlib.sha256(name.lower().encode()).hexdigest(), 16)
    while True:
        w = (SYL[h % 18] + SYL[(h // 18) % 18] + SYL[(h // 324) % 18]).capitalize()
        if w not in taken:
            return w
        h //= 7


def _camel(word):
    """'Braroskel' → 'BraRoskel': the invented name split at its first syllable, so a CamelCase brand stays CamelCase."""
    for syl in sorted(SYL, key=len, reverse=True):
        if word.lower().startswith(syl) and len(word) > len(syl):
            return word[:len(syl)].capitalize() + word[len(syl):].capitalize()
    return word


def _case_like(src, word):
    if src.isupper() and len(src) > 1:
        return word.upper()
    if src.islower():
        return word.lower()
    if re.fullmatch(r'[A-Z][a-z]+[A-Z][A-Za-z]+', src):     # "an employer", "DoorDash": tests read the CamelCase shape
        return _camel(word)
    return word


def _fictional(text, pairs):
    """Test files: each company → its own invented name, case-insensitive and case-preserving, also the squashed form used
    in domains ("a Greenhouse employer" → imctrading.com), so tests that match a sender against the tracker company still pass."""
    taken = set()
    names = {n.lower() for _, _, n in pairs}
    for rx, _, name in pairs:
        # "an employer" when "Amazon" is also applied: left to the shorter name, so both read as one company
        if any(name.lower() != n and re.match(re.escape(n) + r'(?![A-Za-z0-9])', name.lower()) for n in names):
            continue
        f = fictional_name(name, taken); taken.add(f)
        if DATED in rx:                                  # an English word ("Square", "Box"): exact case and only as a dated
            text = re.sub(r'(?<![A-Za-z0-9])' + re.escape(name) + r'(?![A-Za-z0-9])' + DATED, f, text)   # reference, never "box(" or an option "Workshop"
            continue
        forms = {name, re.sub(r'[^A-Za-z0-9]', '', name)}
        for form in sorted(forms, key=len, reverse=True):
            if len(form) < 3:
                continue
            # a short all-caps name ("an employer", "a Greenhouse employer", "POET") only in its own case: never the month "Nov" or the word "poet"
            fl = 0 if (form.isupper() and len(form) <= 4) else re.I
            text = re.sub(r'(?<![A-Za-z0-9])' + re.escape(form) + r'(?![A-Za-z0-9])', lambda m: _case_like(m.group(0), f), text, flags=fl)
        sq = re.sub(r'[^A-Za-z0-9]', '', name)
        if len(sq) >= 6:                                 # spaced / dotted spellings of a squashed name ("an employer" → "JPMorgan Chase")
            rx = r"[\s.&'-]?".join(re.escape(ch) for ch in sq)
            text = re.sub(r'(?<![A-Za-z0-9])' + rx + r'(?![A-Za-z0-9])', lambda m: _case_like(m.group(0), f), text, flags=re.I)
    return text


def _sub_companies(text, pairs):
    keep = []
    def hold(m):
        keep.append(m.group(0)); return '\x00%d\x00' % (len(keep) - 1)
    text = PROTECT.sub(hold, text)
    for rx, label, *_ in pairs:
        text = re.sub(rx, label, text)
    return re.sub(r'\x00(\d+)\x00', lambda m: keep[int(m.group(1))], text)


def generic_companies(text, ext, pairs, path=''):
    """Pure (tested). Replace the user's applied companies: in docs / data files with a generic label ("a Workday employer");
    in test files with a stable invented name per company; in code (.py .js .sh) only inside comments (# … / // …) and
    Python docstrings, never in the code itself."""
    if not pairs:
        return text
    base = os.path.basename(path)
    if re.match(r'(t_|test_|_test_).*|.*_test\.js$|.*_cases\.json$', base) or '/test/' in path:
        keep = []
        def hold(m):
            keep.append(m.group(0)); return '\x00%d\x00' % (len(keep) - 1)
        return re.sub(r'\x00(\d+)\x00', lambda m: keep[int(m.group(1))], _fictional(PROTECT.sub(hold, text), pairs))
    if ext not in ('py', 'js', 'sh', 'mjs'):
        return _sub_companies(text, [(rx.replace(DATED, ''), l, n) for rx, l, n in pairs])
    out, in_doc = [], False
    for line in text.split('\n'):
        n = sum(line.count(q) for q in DOCQ) if ext == 'py' else 0
        if in_doc or (n and line.lstrip().startswith(DOCQ)):
            out.append(_sub_companies(line, pairs))
            if n % 2 == 1:
                in_doc = not in_doc
            continue
        m = re.search(r'(^|\s)(#|//)(?!/)', line)
        out.append(line[:m.start()] + _sub_companies(line[m.start():], pairs) if m else line)
    return '\n'.join(out)


def drop_private_lines(text, path):
    """Pure (tested). Markdown: drop every line that starts with "Seen:" — the private evidence under a problem type in a skill
    (which companies / dates showed it; Joey 2026-11-02: 「我自己的文件可以保留这些公司名，推送到 GitHub 上的要去掉」)."""
    if not path.endswith('.md'):
        return text
    return ''.join(l for l in text.splitlines(keepends=True) if not l.lstrip().startswith('Seen:'))   # keeps the other lines' own breaks


def public_data(path):
    """Pure. True for public brand data and its tests: exported without company-name replacement."""
    return path in PUBLIC_DATA or (path.startswith('scripts/test_cases/') and os.path.basename(path).startswith(PUBLIC_DATA_CASES))


def keep(path):
    """Pure (tested). A repo-relative path → True when it belongs in the public tree."""
    p = path.replace('\\', '/')
    while p.startswith('./'):
        p = p[2:]                                        # not lstrip('./'): that also ate the dot of .claude/ (2026-11-02)
    if p in ALLOW:
        return True
    if p.startswith('config/'):
        return p in CONFIG_PUBLIC or '.example.' in os.path.basename(p) or p.startswith('config/fixtures/')   # fixtures = fictional test people
    if p in DENY_FILES or p in PRIVATE_TESTS or any(p.startswith(d) for d in DENY_DIRS):
        return False
    if p.startswith('scripts/test_cases/') and os.path.basename(p).startswith(PRIVATE_CASES):
        return False
    if any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(os.path.basename(p), g) for g in DENY_GLOBS):
        return False
    return True


VERSION = re.compile(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?')


def parse_version(v):
    """Pure (tested). "v0.2" / "v1.4.3" → (0, 2, 0) / (1, 4, 3); anything else (no "v", leading zeros, extra parts) → None."""
    m = VERSION.fullmatch((v or '').strip()) if isinstance(v, str) and v == v.strip() else None
    return tuple(int(x or 0) for x in m.groups()) if m else None


def release_message(version):
    """Pure (tested). The commit subject of a public release."""
    return f'auto-job-search-agent {version} (public export)'


def preflight(version, tags, dirty, behind, branch, has_commits):
    """Pure (tested). Can CLONE take release `version`? → list of problem codes, [] = go.
    bad_version · no_history (not a clone of the public repo) · not_main · dirty (uncommitted or untracked files) ·
    behind (the remote has commits this clone lacks: pull first, e.g. a merged outside PR) · tag_exists · not_newer
    (not above the highest existing version tag; tags that are not versions are ignored)."""
    errs, nv = [], parse_version(version)
    if nv is None:
        errs.append('bad_version')
    if not has_commits:
        errs.append('no_history')
    elif branch != 'main':
        errs.append('not_main')
    if dirty:
        errs.append('dirty')
    if behind:
        errs.append('behind')
    if nv is not None:
        if version in (tags or []):
            errs.append('tag_exists')
        else:
            old = [parse_version(t) for t in tags or []]
            if any(o is not None and o >= nv for o in old):
                errs.append('not_newer')
    return errs


def stale_paths(clone_tracked, exported):
    """Pure (tested). Files tracked in the public clone that the new export no longer has → remove them (sorted).
    Never touches anything inside .git/."""
    keepset = {p.replace('\\', '/') for p in exported}
    return sorted({p.replace('\\', '/') for p in clone_tracked if p and not (p == '.git' or p.startswith('.git/'))} - keepset)


def tree_files(d):
    return sorted(os.path.relpath(os.path.join(b, f), d) for b, ds, fs in os.walk(d) for f in fs
                  if not os.path.relpath(b, d).split(os.sep)[0] == '.git')


def update(a):
    """--update CLONE --version vX.Y: one normal release commit + tag in the public clone, nothing pushed (JSA-089)."""
    import tempfile
    clone, version = os.path.abspath(a[a.index('--update') + 1]), a[a.index('--version') + 1] if '--version' in a else ''
    g = lambda *x, check=True: subprocess.run(['git', '-C', clone, *x], capture_output=True, text=True, check=check)
    if not os.path.isdir(os.path.join(clone, '.git')):
        print(f'{clone}: not a git clone of the public repo'); return 2
    has = g('rev-parse', '--verify', '-q', 'HEAD', check=False).returncode == 0
    if g('remote', check=False).stdout.strip():
        f = g('fetch', '-q', '--tags', check=False)
        if f.returncode:
            print('warning: git fetch failed — cannot tell whether the remote moved:', f.stderr.strip()[:200])
    up = g('rev-list', '--count', 'HEAD..@{u}', check=False)
    errs = preflight(version, g('tag', '--list').stdout.split(), bool(g('status', '--porcelain').stdout.strip()),
                     int(up.stdout.strip() or 0) if up.returncode == 0 else 0,
                     g('symbolic-ref', '--short', '-q', 'HEAD', check=False).stdout.strip(), has)
    if errs:
        hint = {'bad_version': 'use vMAJOR.MINOR[.PATCH], e.g. v0.2', 'no_history': 'clone the public repo first (git clone …)',
                'not_main': 'git checkout main', 'dirty': 'commit or remove local changes in the clone',
                'behind': 'git pull --ff-only (the remote has new commits)', 'tag_exists': 'pick the next version',
                'not_newer': 'the version must be above the highest existing tag'}
        for e in errs:
            print(f'preflight: {e} — {hint[e]}')
        return 2
    tmp = tempfile.mkdtemp(prefix='jsa_export_')
    try:
        out = os.path.join(tmp, 'tree')
        rc = main(['--out', out])                         # export + scan; any hit → stop before the clone is touched
        if rc:
            print('update aborted: export / scan failed, clone untouched'); return rc
        tcopy = os.path.join(tmp, 'testrun')
        shutil.copytree(out, tcopy, symlinks=True)        # tests rewrite fixtures: run them on a throwaway copy
        print('running scripts/test_all.sh in the exported tree …', flush=True)
        t = subprocess.run(['bash', 'scripts/test_all.sh'], cwd=tcopy, capture_output=True, text=True)
        print('\n'.join(t.stdout.strip().splitlines()[-6:]))
        if t.returncode:
            print('update aborted: tests failed, clone untouched'); return 1
        new = tree_files(out)
        for p in stale_paths(g('ls-files', '-z').stdout.split('\0'), new):
            os.remove(os.path.join(clone, p))
            d = os.path.dirname(os.path.join(clone, p))
            while d != clone and os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d); d = os.path.dirname(d)
        for p in new:
            dst = os.path.join(clone, p)
            if os.path.isdir(dst) and not os.path.islink(dst):
                shutil.rmtree(dst)
            os.makedirs(os.path.dirname(dst) or clone, exist_ok=True)
            shutil.copy2(os.path.join(out, p), dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    hits = scan.scan_tree(clone)                          # the clone as it will be committed (ignored files included)
    if hits:
        for h in hits[:40]:
            print('  HIT', h)
        print(f'scan of the clone: {len(hits)} hit(s) — not committed; git -C {clone} checkout -- . && git -C {clone} clean -fd to undo')
        return 1
    g('add', '-A')
    if g('diff', '--cached', '--quiet', check=False).returncode == 0:
        print('nothing changed since the last release — no commit'); return 3
    stat = g('diff', '--cached', '--shortstat').stdout.strip()
    g('commit', '-q', '-m', release_message(version)); g('tag', '-a', version, '-m', release_message(version))
    print(f'git: {release_message(version)} on main ({stat}), tag {version}. Nothing pushed.')
    print(f'push (after Joey says yes): git -C {clone} push origin main {version}')
    return 0


def tracked():
    out = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z'], capture_output=True, check=True).stdout.decode('utf-8')
    return [p for p in out.split('\0') if p]


def main(a):
    if '--update' in a:
        return update(a)
    files = [p for p in tracked() if keep(p)]
    if '--list' in a:
        print('\n'.join(files)); print(f'{len(files)} files', file=sys.stderr); return 0
    if '--out' not in a:
        print(__doc__); return 2
    out = os.path.abspath(a[a.index('--out') + 1])
    if os.path.exists(out):
        print(f'{out} exists — choose a new folder'); return 2
    cj = lambda n: json.load(open(os.path.join(ROOT, 'config', n), encoding='utf-8'))
    pairs = pseudo_pairs(cj('profile.json'), cj('profile.example.json'), os.path.expanduser('~'))
    jl = lambda n: [json.loads(l) for l in open(jpaths.data('store', n), encoding='utf-8') if l.strip()] \
        if os.path.exists(jpaths.data('store', n)) else []
    words = set(w.strip().lower() for w in open('/usr/share/dict/words')) if os.path.exists('/usr/share/dict/words') else set()
    cpairs = company_pairs(jl('applications.jsonl'), jl('jobs.jsonl'), words)   # the user's applied companies → generic labels
    for p in files:
        dst = os.path.join(out, _fictional(p, cpairs) if '/test/' in p else p)   # test fixtures named after a company
        os.makedirs(os.path.dirname(dst) or out, exist_ok=True)
        if p == 'LICENSE':
            shutil.copy2(os.path.join(ROOT, p), dst); continue
        try:
            text = open(os.path.join(ROOT, p), encoding='utf-8').read()
        except UnicodeDecodeError:
            shutil.copy2(os.path.join(ROOT, p), dst); continue      # binaries are refused by keep(); the scan reports any left
        text = pseudonymize(drop_private_lines(text, p), pairs)
        if p not in ALLOW and not public_data(p):           # the PERM list / H-1B brand names are public data, not the user's history
            text = generic_companies(text, p.rsplit('.', 1)[-1], cpairs, p)
        open(dst, 'w', encoding='utf-8').write(text)
        shutil.copymode(os.path.join(ROOT, p), dst)
    for src, dst in SWAP.items():
        if os.path.exists(os.path.join(ROOT, src)):
            os.makedirs(os.path.dirname(os.path.join(out, dst)) or out, exist_ok=True)
            shutil.copy2(os.path.join(ROOT, src), os.path.join(out, dst))
    open(os.path.join(out, '.jsa-public'), 'w').write('public export: scripts/test_all.sh runs the tests against config/fixtures/f1_student\n')
    with open(os.path.join(out, '.gitignore'), 'a', encoding='utf-8') as f:   # the user's own data never gets committed
        f.write('\n# personal data (public export, JSA-078)\nconfig/*.json\n!config/*.example.json\nconfig/resume_content.py\n'
                'skills/auto-apply/scripts/cx_bundle.js\napplications/\ndata/store/\ndata/runner/\nresume/\n')
    hits = scan.scan_tree(out)
    print(f'exported {len(files)} files to {out}')
    if hits:
        for h in hits[:80]:
            print('  HIT', h)
        print(f'scan: {len(hits)} hit(s) — not publishable'); return 1
    print('scan: 0 hits')
    if '--git' in a:
        g = lambda *x: subprocess.run(['git', '-C', out, *x], check=True, capture_output=True)
        g('init', '-q', '-b', 'main'); g('add', '-A'); g('commit', '-q', '-m', release_message('v0.1'))
        g('tag', '-a', 'v0.1', '-m', release_message('v0.1'))
        print('git: one root commit on main, tag v0.1 (nothing pushed); later releases: --update <clone> --version v0.2')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
