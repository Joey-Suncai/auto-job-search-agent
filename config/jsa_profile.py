"""Loads the candidate profile (JSA-077): $JSA_PROFILE → config/profile.json → config/profile.example.json.
Python: sys.path.insert(0, <repo>/config); import jsa_profile; P = jsa_profile.load(); jsa_profile.get('contact.email').
page_js() = the lines that install the profile (+ the referrer pool, pool()) in a browser page before answer_rules.js is evaluated."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
try:
    import paths  # noqa: E402  (the data home: $JSA_HOME, else this repo — ADR-0008)
except ImportError:                                   # copied on its own (a test's temp dir): the old layout
    class paths:  # noqa: N801
        home = staticmethod(lambda: ROOT)
        config = staticmethod(lambda *p: os.path.join(HERE, *p))
_cache = {}


def path():
    for p in (os.environ.get('JSA_PROFILE'), paths.config('profile.json'), os.path.join(HERE, 'profile.json'), os.path.join(HERE, 'profile.example.json')):
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError('no profile: copy config/profile.example.json to config/profile.json')


def load():
    p = path()
    if p not in _cache:
        with open(p, encoding='utf-8') as f:
            _cache[p] = json.load(f)
    return _cache[p]


def get(dotted, default=None):
    """'contact.email' → value; a missing key returns `default`."""
    v = load()
    for k in dotted.split('.'):
        if not isinstance(v, dict) or k not in v:
            return default
        v = v[k]
    return v


def repo_path(dotted):
    """A profile path (relative to the repo) → absolute path, or None."""
    v = get(dotted)
    return os.path.join(paths.home(), v) if v else None        # relative to the data home (= the repo until JSA_HOME is set)


def data_file(name, env=None):
    """config/<name> (the user's file) → config/<stem>.example<ext> when the user has none yet; $env overrides both."""
    if env and os.environ.get(env):
        return os.environ[env]
    for p in (paths.config(name), os.path.join(HERE, name)):     # the data home's config/, then the repo's (old layout)
        if os.path.exists(p):
            return p
    stem, ext = os.path.splitext(name)
    return os.path.join(HERE, stem + '.example' + ext)


def use_fixture_if_no_user(name='f1_student'):
    """Tests (JSA-086): when the user has no config/profile.json (a fresh public clone), point every config file at the
    fictional fixture config/fixtures/<name>/ so tests that check one kind of candidate (e.g. F-1 / CPT) still run.
    The private repo keeps testing the real files. Call before importing canon / plan_build / run_wd."""
    if os.path.exists(paths.config('profile.json')) or os.path.exists(os.path.join(HERE, 'profile.json')) or os.environ.get('JSA_PROFILE'):
        return False
    d = os.path.join(HERE, 'fixtures', name)
    for env, f in (('JSA_PROFILE', 'profile.json'), ('JSA_CANONICAL', 'canonical.json'), ('JSA_WD_PROFILE', 'wd_profile.json')):
        if os.path.exists(os.path.join(d, f)):
            os.environ[env] = os.path.join(d, f)
    _cache.clear()
    return True


def pool():
    """The referrer pool (JSA-195): config/connections.json → {'connections': {company key: [[name, headline]]}, 'aliases': {…}}
    — 1st-degree people at their CURRENT company ($JSA_CONNECTIONS overrides; no file = an empty pool). Same order as
    config/connections.js."""
    p = data_file('connections.json', env='JSA_CONNECTIONS')
    try:
        with open(p, encoding='utf-8') as f:
            raw = json.load(f)
    except OSError:
        raw = {}
    return {'connections': raw.get('connections') or {}, 'aliases': raw.get('aliases') or {}}


def page_js():
    """The lines that install the profile and the referrer pool in a browser page before answer_rules.js is evaluated."""
    return ('globalThis.__cxProfile = ' + json.dumps(load(), ensure_ascii=False) + ';\n'
            + 'globalThis.__cxPool = ' + json.dumps(pool(), ensure_ascii=False) + ';\n')
