"""Resume content shim (JSA-077, 2026-11-02): the candidate's resume content is personal data and lives in
config/resume_content.py (falls back to config/resume_content.example.py). Scripts keep `import content as C`."""
import importlib.util
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402
_spec = importlib.util.spec_from_file_location('resume_content', jsa_profile.data_file('resume_content.py', 'JSA_RESUME_CONTENT'))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
globals().update({k: v for k, v in vars(_m).items() if not k.startswith('_')})


def lead_on_resume(entries, lead_org):
    """Pure (tested, JSA-255). False when a facts entry of the LEAD block's organisation has on_resume explicitly false (the
    user took the activity off every resume, Joey 2026-11-08) — the Leadership section is then left out; True otherwise."""
    norm = lambda s: ' '.join(str(s or '').split()).lower()
    if not norm(lead_org):
        return True
    return not any(isinstance(e, dict) and norm(e.get('org')) == norm(lead_org) and e.get('on_resume') is False
                   for e in entries or [])


def _lead_on(path=None):
    """LEAD_ON from the facts file: a missing file → True (a fresh install / fixture: the content as written stands); a file
    that exists but cannot be read → False (never put an activity back on a resume because the facts did not parse)."""
    import json
    try:
        if path is None:
            import paths
            path = paths.config('facts.json')
        if not os.path.exists(path):
            return True
        with open(path, encoding='utf-8') as fh:
            entries = (json.load(fh) or {}).get('entries')
        return lead_on_resume(entries, (globals().get('LEAD') or {}).get('org'))
    except Exception:
        return False


LEAD_ON = _lead_on()   # False → no Leadership section in any resume (build_a.py, build_b.js via content.json, ds_materials.py)
