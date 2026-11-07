"""Job Chrome extension guard (JSA-227, Joey 2026-11-06 「只留 Claude，其余都停用」).

The iCloud Passwords extension's dropdown opened the macOS Passwords app while a runner typed (an employer Oracle, 11-06), and
autofill extensions (Simplify, 求职方舟 …) can overwrite what a runner filled. Before a run opens any form, the job Chrome
profile must have no extension enabled except: Claude, the agent's own unpacked Lever fill, and Chrome's own component
extensions (PDF viewer, Docs Offline, Web Store Payments …). Read from the profile's `Secure Preferences` file (no tab, no
browser call). An unreadable file never blocks (the guard reports nothing).
"""
import json, os

PROFILE = os.environ.get('JSA_CHROME_PROFILE', os.path.expanduser('~/.job-agent-chrome'))
ALLOWED_IDS = {
    'fcoeoabgfenejglbffodgkkbkcdhcgfn': 'Claude',
    'ghbmnnjooekpmoecnnnilnnbdlolhkhi': 'Google Docs Offline (Chrome default)',
    'nmmhkkegccagdldgiimedpiccmgmieda': 'Chrome Web Store Payments (Chrome default)',
}
COMPONENT = (5, 10)          # Chrome's own component extensions (location codes)
UNPACKED = 4                 # loaded from a folder: allowed only for the agent's own Lever fill


def enabled_others(settings):
    """Pure (tested). settings = Secure Preferences → extensions.settings. Returns [(id, name)] of enabled extensions that
    are not allowed. Enabled = it has a manifest and an empty (or missing) disable_reasons list and is not blocklisted."""
    out = []
    for eid, v in (settings or {}).items():
        if not isinstance(v, dict):
            continue
        man = v.get('manifest') or {}
        if not man:
            continue                                        # a stub entry (no manifest): nothing installed
        reasons = v.get('disable_reasons')
        if reasons not in (None, [], 0) or v.get('blacklist_state') or v.get('state') == 0:
            continue                                        # disabled
        loc = v.get('location')
        if eid in ALLOWED_IDS or loc in COMPONENT:
            continue
        name = man.get('name') or eid
        if loc == UNPACKED and 'lever_fill' in str(v.get('path') or '').replace('\\', '/'):
            continue                                        # skills/auto-apply/lever_fill (the agent's own)
        out.append((eid, name))
    return out


def problems(profile=None):
    """[] when the job Chrome is clean (or the file cannot be read); else one problem line naming the extensions."""
    if profile is None and os.environ.get('CX_DATA') and not os.environ.get('JSA_CHROME_PROFILE'):
        return []                                           # test mode (CX_DATA): never read the real job Chrome
    p = os.path.join(profile or PROFILE, 'Default', 'Secure Preferences')
    try:
        settings = json.load(open(p, encoding='utf-8')).get('extensions', {}).get('settings', {})
    except (OSError, ValueError):
        return []
    bad = enabled_others(settings)
    if not bad:
        return []
    names = ', '.join(n for _, n in bad)
    return [f'job Chrome has other extensions enabled ({names}) — disable them in chrome://extensions of the job Chrome '
            f'(Joey 2026-11-06: only Claude); autofill / password extensions interfere with the runner']


def stop(folder, url, log, queue=None, data=None, ats=''):
    """For runners without runner_common: True = stopped (results line, queue line, STATUS blocked printed)."""
    bad = problems()
    if not bad:
        return False
    import time
    log('NOT started: ' + bad[0])
    if queue and folder:
        try: queue(folder, bad[0][:300], url)
        except Exception: pass
    if data:
        os.makedirs(data, exist_ok=True)
        with open(os.path.join(data, 'results.jsonl'), 'a') as out:
            out.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'folder': os.path.basename(folder or ''), 'url': url,
                                  'ats': ats, 'status': 'blocked', 'problems': bad, 'mode': 'gate'}) + '\n')
    print('STATUS blocked')
    return True
