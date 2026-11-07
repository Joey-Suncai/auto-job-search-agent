#!/usr/bin/env python3
"""Render the LaunchAgent templates in scripts/launchagent/*.plist for this Mac and (optionally) load them (JSA-079).

The repo copies are templates: {{REPO}} = the code the routines run (the release ~/JobAgent/app once scripts/release.py made
one — ADR-0008 — else this checkout), {{PYTHON}} = a python3 for the stdlib routines,
{{VENV_PYTHON}} = the venv python with Playwright / python-docx / anthropic (setup.sh creates it).
usage: python3 scripts/launchagent/install.py [--only refresh,gate] [--out ~/Library/LaunchAgents] [--load] [--check]
                                              [--repo DIR] [--python PATH] [--venv-python PATH]
  default   write the rendered plists to --out (nothing is loaded)
  --check   write nothing; print which installed plists differ from the rendered ones (exit 1 if any)
  --load    after writing, `launchctl bootout` + `bootstrap` each one (the routine starts on its schedule)
Tests (rule 13): scripts/test_launchagent_render.py with DeepSeek cases.
"""
import glob, os, re, shutil, subprocess, sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KEYS = ('REPO', 'PYTHON', 'VENV_PYTHON')


def render(text, values):
    """Pure (tested). Replace {{KEY}} with the XML-escaped value; an unknown or empty placeholder is an error."""
    def sub(m):
        k = m.group(1)
        if not values.get(k):
            raise ValueError(f'no value for {{{{{k}}}}}')
        return escape(str(values[k]))
    return re.sub(r'\{\{([A-Z_]+)\}\}', sub, text)


def defaults(a):
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    rel = os.path.expanduser(os.environ.get('JSA_APP') or '~/JobAgent/app')   # the release, once there is one (ADR-0008)
    repo = arg('--repo', rel if os.path.exists(os.path.join(rel, '.jsa-release')) else ROOT)
    return {'REPO': os.path.abspath(repo),
            'PYTHON': arg('--python', next((p for p in ('/opt/homebrew/bin/python3', '/usr/local/bin/python3') if os.path.exists(p)), None) or shutil.which('python3') or '/usr/bin/python3'),   # Homebrew first: launchd has no shell PATH
            'VENV_PYTHON': arg('--venv-python', os.path.expanduser(os.environ.get('JSA_VENV', '~/.job-agent-venv')) + '/bin/python')}


def main(a):
    vals = defaults(a)
    out = os.path.expanduser(a[a.index('--out') + 1] if '--out' in a else '~/Library/LaunchAgents')
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    files = sorted(f for f in glob.glob(os.path.join(HERE, 'com.jobagent.*.plist'))
                   if not only or os.path.basename(f).split('.')[2] in only)
    differ = []
    for f in files:
        name = os.path.basename(f)
        text = render(open(f, encoding='utf-8').read(), vals)
        dst = os.path.join(out, name)
        if '--check' in a:
            if not os.path.exists(dst) or open(dst, encoding='utf-8').read() != text:
                differ.append(name)
            continue
        os.makedirs(out, exist_ok=True)
        open(dst, 'w', encoding='utf-8').write(text)
        print('wrote', dst)
        if '--load' in a:
            dom = f'gui/{os.getuid()}'
            subprocess.run(['launchctl', 'bootout', f'{dom}/{name[:-6]}'], capture_output=True)
            r = subprocess.run(['launchctl', 'bootstrap', dom, dst], capture_output=True, text=True)
            print('  loaded' if r.returncode == 0 else f'  launchctl: {r.stderr.strip()}')
    if '--check' in a:
        print('all installed plists match' if not differ else 'differ from the templates: ' + ', '.join(differ))
        return 1 if differ else 0
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
