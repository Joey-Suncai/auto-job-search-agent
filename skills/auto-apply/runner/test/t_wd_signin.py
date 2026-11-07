#!/usr/bin/env python3
"""Offline tests for wd_signin.py against test/mock_wd_signin.html (headless Chromium, no network, no Keychain).
   ~/.job-agent-venv/bin/python test/t_wd_signin.py     → prints `fails 0`"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import wd_signin
from run import launch_browser
from playwright.sync_api import sync_playwright

TMP = tempfile.mkdtemp()
MOCK = 'file://' + os.path.join(HERE, 'mock_wd_signin.html')
fails = 0
def T(name, ok, got=''):
    global fails
    fails += (not ok); print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  -> {got}'))

# like wd_page.js __wdAuth: a visible password field, or an auth step heading (Sign In / Create Account)
auth = lambda page: (lambda: page.evaluate("() => [...document.querySelectorAll('input[type=password]')].some(e => e.offsetParent !== null) || /^(sign in|create account)/i.test((document.querySelector('h2') || {}).textContent || '')"))
logs = []
with sync_playwright() as pw:
    br = launch_browser(pw)
    def fresh(mode):
        ctx = br.new_context(); page = ctx.new_page()
        page.goto(MOCK + '#' + mode); page.evaluate('localStorage.clear()'); page.reload(); return page

    p = fresh('account')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p))
    T('existing account → signed in', ok, why)

    p = fresh('new')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p))
    T('no account → create account → signed in', ok, why)
    T('account terms box was ticked and passwords matched', p.evaluate("localStorage.getItem('mock_pw')") == 'pw-right')

    p = fresh('verify')
    link = MOCK.replace('#', '') + '?verifyToken=abc'
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p),
                                    find_link=lambda **k: link, verify_timeout=5)
    T('create → verify e-mail link → sign in', ok, why)

    p = fresh('verify')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p),
                                    find_link=lambda **k: None, verify_timeout=1)
    T('verification mail never arrives → hand to Joey', (not ok) and 'verification' in why, why)

    p = fresh('relogin')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p))
    T('create → tenant shows the sign-in box again → signs in (Talkellum)', ok, why)

    p = fresh('social')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p))
    T('social chooser → Sign in with email → create → signed in (Fenwynhar)', ok, why)

    p = fresh('captcha')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p))
    T('CAPTCHA → hand to Joey', (not ok) and 'CAPTCHA' in why, why)

    p = fresh('account')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-wrong', is_auth=auth(p))
    T('wrong password on an existing account → hand to Joey (one create try at most)', not ok, why)

    # JSA-207: after the create-account form, sign-in still fails — the reason names the case and what Joey does
    p = fresh('oldacct')
    old_mail = lambda url: [{'date': '2025-10-21', 'kind': 'other', 'subject': 'Thank you for Applying!'}]
    ok, why = wd_signin.auto_signin(p, logs.append, folder=TMP, password='pw-right', is_auth=auth(p), mail_history=old_mail, settle=3)
    T('create → silent sign-in box → wrong password, tenant mail from 2025 → old_account', (not ok) and '[old_account]' in why and 'old password' in why, why)
    rec = json.load(open(os.path.join(TMP, 'signin.json')))
    T('signin.json records the code and the tenant message', rec.get('code') == 'old_account' and 'Wrong email or password' in rec.get('signin_msg', ''), rec)

    p = fresh('oldacct')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p), mail_history=lambda url: [], settle=3)
    T('same, but no mail from this tenant at all → no_verify_mail', (not ok) and '[no_verify_mail]' in why, why)

    p = fresh('lateverify')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p), find_link=lambda **k: link, settle=3)
    T("an earlier run's unverified account → its link from Gmail → signed in", ok, why)

    p = fresh('lateverify')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p), find_link=lambda **k: None,
                                    mail_history=lambda url: [], settle=3)
    T('unverified and no link in Gmail → no_verify_mail', (not ok) and '[no_verify_mail]' in why, why)

    p = fresh('locked')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-right', is_auth=auth(p), settle=3)
    T('"account locked" → locked, no Create Account try', (not ok) and '[locked]' in why and not p.locator('[data-automation-id=verifyPassword]').count(), why)

    p = fresh('account')
    ok, why = wd_signin.auto_signin(p, logs.append, password='pw-wrong', is_auth=auth(p), settle=3)
    T('wrong password, tenant says the account exists → old_account', (not ok) and '[old_account]' in why, why)

    p = fresh('account')
    ok, why = wd_signin.auto_signin(p, logs.append, password='', is_auth=auth(p))
    T('no Keychain password → hand to Joey', (not ok) and 'Keychain' in why, why)
    br.close()

T('the password never appears in the log', not any('pw-right' in l or 'pw-wrong' in l for l in logs), logs)
print(f'fails {fails}')
sys.exit(1 if fails else 0)
