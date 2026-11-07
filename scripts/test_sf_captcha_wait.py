#!/usr/bin/env python3
"""run_successfactors.captcha_wait — minutes to wait for the candidate's reCAPTCHA tick (Erie 2026-11-05: a dry run can
wait when --wait-captcha is given). Cases by DeepSeek from scripts/test_cases/sf_captcha_wait_spec.md (rule 13).
    python3 scripts/test_sf_captcha_wait.py"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import run_successfactors as R  # noqa: E402

cases = json.load(open(os.path.join(ROOT, 'scripts', 'test_cases', 'sf_captcha_wait_cases.json')))
bad = 0
for c in cases:
    got = R.captcha_wait(c['submit'], c['given'])
    if not (isinstance(got, float) and abs(got - float(c['expect'])) < 1e-9):
        bad += 1; print('FAIL', c['name'], c['submit'], c['given'], 'got', got, 'want', c['expect'])
print(f'{len(cases)} cases · ' + ('ALL PASS' if not bad else f'{bad} FAILED')); sys.exit(1 if bad else 0)
