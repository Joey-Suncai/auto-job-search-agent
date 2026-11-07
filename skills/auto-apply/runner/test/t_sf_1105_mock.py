#!/usr/bin/env python3
"""Offline page checks for the SuccessFactors fixes after the 2026-11-05 batch (JSA-092 types S, T) — a headless Chromium of
its own on inline HTML (never the job Chrome, no network):
  1. a chat iframe over "Apply now" (Danfoss: #phenomChatbotIframe) is hidden, the cookie banner is left alone, Apply clicks;
  2. a register form: the "… data privacy agreement" link is opened and accepted (Newell), the "Make My Profile Visible to"
     radio group is answered from config (profile_visibility) — and with no answer it goes to needs-user;
  3. (types W, X, Y) no-id radios, the one-page register-and-apply form, short inverted school names;
  4. (type AF) the final #fbqa_apply under a fixed cookie banner: hidden from view for the click only, its buttons never
     pressed; a session dialog over Apply → stop, "Apply not pressed";
  5. (type AE) education rows with UI5 From / To Date pickers before School: typed from the facts without Enter, read back,
     no start on file → ask Joey.
    ~/.job-agent-venv/bin/python skills/auto-apply/runner/test/t_sf_1105_mock.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..', 'config'))
import run_successfactors as S  # noqa: E402
import jsa_profile  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

JOB = """<html><body>
<div id="onetrust-banner-sdk" style="position:fixed;bottom:0;left:0;width:100%;height:60px;background:#eee">We use cookies <button>Close</button></div>
<div style="padding:40px"><a id="apply" href="/talentcommunity/apply/123/" onclick="window.clicked=1;return false;" style="display:inline-block;padding:10px">Apply now</a></div>
<iframe id="phenomChatbotIframe" title="Phenom Career Bot" style="position:fixed;top:0;left:0;width:100%;height:100%;border:0;background:transparent" srcdoc="<p>Hi! I am the Career Bot</p>"></iframe>
</body></html>"""

REG = """<html><body>
<div class="row"><label for="fbclc_userName">Email</label><input id="fbclc_userName"></div>
<div class="row"><div class="q">* Make My Profile Visible to:</div>
  <div><input type="radio" name="fbclc_visibility" id="v1" value="1"><label for="v1">Any Acme recruiter worldwide</label></div>
  <div><input type="radio" name="fbclc_visibility" id="v2" value="2"><label for="v2">Any Acme recruiter in my country/region</label></div>
  <div><input type="radio" name="fbclc_visibility" id="v3" value="3"><label for="v3">Only recruiters managing jobs I apply to</label></div></div>
<p id="err">Please open the data privacy agreement and accept it.</p>
<a href="#" id="dpa" onclick="document.getElementById('sfOverlayMgr').style.display='block';return false;">Read and accept the data privacy agreement</a>
<div id="sfOverlayMgr" style="display:none"><button onclick="document.getElementById('ok').textContent='The data privacy agreement has been accepted.';document.getElementById('sfOverlayMgr').style.display='none'">Accept</button></div>
<p id="ok"></p>
</body></html>"""

VIS = {'pick': ['/^any\\b.{0,80}\\brecruiters?\\b.{0,30}\\bworldwide\\b/i'], 'text': 'Any recruiter worldwide'}

# Newell 11-05 (second run), the real structure with a fictional company: radios with NO id and NO <label for>; the option
# text is in aria-label and in a loose <label> after the input's wrapper span (the TimeoutError: radio_set looked up [id=""]).
O1 = 'Any Acme recruiter worldwide (Selecting this option will enable us (for the duration indicated in the privacy policy below) to contact you about other opportunities globally)'
O2 = 'Any Acme recruiter in my country/region of residence (Selecting this option will enable us to contact you about other opportunities in the country/countries to which you have applied)'
O3 = 'Only recruiters managing jobs I apply to: (If you select this option, we will not be able to contact you about any other opportunities)'
REG2 = '<html><body><table><tr><td><label for="fbclc_userName">Email Address:</label></td><td><input id="fbclc_userName"></td></tr>' \
       '<tr><td>Make My Profile Visible to:<span class="required">*</span></td><td>' + ''.join(
           f'<div class="displayCenter"><span class="visibility_option_error"><input onclick="window.vis=this.value" role="radio" class="radioSize" type="radio" '
           f'aria-label="{o}\n" name="fbclc_searPref" value="{v}"></span><label>{o}\n</label></div>' for o, v in ((O1, '1'), (O2, '0'), (O3, '2'))) + \
       '</td></tr></table></body></html>'

# Danfoss 11-05 (career2.successfactors.eu): ONE page holding the CV upload, the fbclc_ account fields, the questions, the
# "Read and accept terms of use" link (DPCS dialog → hidden #fbclc_dpcsId) and #fbqa_apply — no sign-in box, no Create link.
DANFOSS = """<html><head><style>.displayNone{display:none}</style></head><body>
<p>For everyone else: <a href="#">Please sign in.</a></p>
<div><label>* CV/Resume</label><span id="73:_attachLabel">Upload a CV</span>
 <div id="73:_attachDownloadLabel" class="displayNone"><span id="73:_attachDownloadLabelLink">Upload a CV</span></div>
 <span id="73:_attachIcon" role="button" onclick="dlg('upload')">+</span></div>
<div id="sfOverlayMgr" style="display:none"></div>
<script>
function dlg(kind) {                                     // SuccessFactors opens every dialog inside #sfOverlayMgr
  const m = document.getElementById('sfOverlayMgr');
  m.innerHTML = kind === 'upload' ? '<input type="file" onchange="uploaded(this)">' : '<p>Terms of use …</p><button onclick="accepted()">Accept</button>';
  m.style.display = 'block';
}
function uploaded(i) { document.getElementById('73:_attachDownloadLabelLink').textContent = i.files[0].name;
  document.getElementById('73:_attachDownloadLabel').classList.remove('displayNone'); document.getElementById('sfOverlayMgr').style.display = 'none'; }
function accepted() { document.getElementById('fbclc_dpcsId').value = '12345'; const p = document.createElement('p'); p.textContent = 'Data privacy statement has been accepted.';
  document.querySelector('.dpcsHyperlink').appendChild(p); document.getElementById('sfOverlayMgr').style.display = 'none'; }
</script>
<table>
<tr><td><label for="fbclc_userName">Email Address: *</label></td><td><input id="fbclc_userName" aria-required="true"></td></tr>
<tr><td><label for="fbclc_emailConf">Retype Email Address: *</label></td><td><input id="fbclc_emailConf" aria-required="true"></td></tr>
<tr><td><label for="fbclc_pwd">Choose Password: *</label></td><td><input type="password" id="fbclc_pwd"><p>Password must be at least 8 characters long.</p>
 <p>Password must not be longer than 18 characters.</p></td></tr>
<tr><td><label for="fbclc_pwdConf">Retype Password: *</label></td><td><input type="password" id="fbclc_pwdConf"></td></tr>
<tr><td><label for="fbclc_fName">First Name: *</label></td><td><input id="fbclc_fName"></td></tr>
<tr><td><label for="fbclc_lName">Last Name: *</label></td><td><input id="fbclc_lName"></td></tr>
<tr><td><label for="fbclc_ituCode">Country/Region Code:*</label></td><td><select id="fbclc_ituCode"><option value="">- Select -</option><option value="GB">United Kingdom (+44)</option>
 <option value="US">United States (+1)</option><option value="UM">United States Minor Outlying Islands (+340)</option></select></td></tr>
<tr><td><label for="fbclc_phoneNumber">Phone Number:*</label></td><td><input id="fbclc_phoneNumber"></td></tr>
<tr><td><label for="sig">Signature*</label></td><td><input id="tor__fcustSignaturePreOffer"></td></tr>
<tr><td><label for="fbclc_country">Country/Region of Residence:*</label></td><td><select id="fbclc_country"><option value="">- Select -</option><option value="US">United States</option></select></td></tr>
<tr><td><label for="fbclc_emailEnabled">Notification:</label></td><td><input type="checkbox" id="fbclc_emailEnabled" checked></td></tr>
<tr><td></td><td><input type="checkbox" id="fbclc_campaignEmailEnabled"><label for="fbclc_campaignEmailEnabled">Hear more about career opportunities.</label></td></tr>
<tr><td><label for="dataPrivacyId">Terms of Use:*</label></td><td class="dpcsHyperlink"><span><a id="dataPrivacyId" role="button" tabindex="0" style="cursor:pointer"
 onclick="dlg('terms');return false;">Read and accept terms of use</a></span><input type="hidden" id="fbclc_dpcsId" value=""></td></tr>
</table>
<button type="submit" id="fbqa_apply" onclick="window.applied=1;return false;">Apply</button>
<a href="#">Privacy policy</a> <a href="#">Danfoss Job Portal Terms</a>
</body></html>"""

# Lumsevsev 11-05: a server-searched College/University list with short inverted names; the first page of the list shows only
# "A…" schools, typing filters by "contains" ("University of Chicago" → no results).
COMBO = """<html><body>
<label for="323:_input">College/University</label>
<input id="323:_input" role="combobox" aria-owns="324:_listSelect" placeholder="No Selection" autocomplete="off">
<ul id="324:_listSelect" style="display:none"></ul>
<script>(() => {                                      // an IIFE: set_content keeps the window, a second top-level const would not load
const inp = document.getElementById('323:_input'), ul = document.getElementById('324:_listSelect');
function show() {
  const q = inp.value.trim().toLowerCase();
  const hits = q ? window.OPTS.filter(o => o.toLowerCase().includes(q)).slice(0, 10) : window.OPTS.slice(0, 3);
  ul.innerHTML = ''; (hits.length ? hits : ['There were no results']).forEach(t => { const li = document.createElement('li'); li.setAttribute('role', 'option'); li.textContent = t;
    li.onclick = () => { if (t !== 'There were no results') { inp.value = t; } ul.style.display = 'none'; }; ul.appendChild(li); });
  ul.style.display = 'block';
}
inp.addEventListener('click', show); inp.addEventListener('input', show);
inp.addEventListener('keydown', e => { if (e.key === 'Escape') ul.style.display = 'none'; });
})();</script></body></html>"""
ACUITY = ['Abilene Christian U', 'Adelphi U', 'Alabama, U of', 'Chicago State U', 'Chicago, U of', 'Illinois State U', 'Illinois, U of/ChUrb',
          'Illinois, U of/Chgo', 'Loyola U Chicago', 'Northwestern U', 'Other']


# AF — Danfoss 11-05 (release-036 rerun): a short page whose #fbqa_apply sits at the bottom under the fixed cookie banner
# (div.cookiePolicy.cookiemanager, z-index 100); the page cannot scroll the button above it. The banner's own buttons record
# a choice — they must never be pressed. COVERED_MODAL: a fixed session dialog over Apply → stop, never hidden.
COVERED = """<html><body style="margin:0">
<div style="height:500px">Questions …</div>
<div style="text-align:right;padding:4px"><button type="submit" id="fbqa_apply" onclick="window.applied=(window.applied||0)+1;return false;">Apply</button></div>
<div class="cookiePolicy cookiemanager " role="region" style="display:block;position:fixed;bottom:0;left:0;width:100%;height:220px;z-index:100;background:#fff">
 <div class="centered"><p>We use cookies to offer you the best possible website experience.</p>
 <button id="cookie-bannershow" onclick="window.cookie='modify'">Modify Cookie Preferences</button>
 <button id="cookie-reject" onclick="window.cookie='reject'">Reject All Cookies</button> <button id="cookie-accept" onclick="window.cookie='accept'">Accept All Cookies</button></div></div>
</body></html>"""
COVERED_MODAL = COVERED.split('<div class="cookiePolicy')[0] + """<div id="sessionTimeout" role="dialog" style="position:fixed;bottom:0;left:0;width:100%;height:220px;z-index:100;background:#fff">
 <p>Your session is about to time out.</p><button onclick="window.extended=1">Continue</button></div></body></html>"""

# AE — Newell 11-05: an education section whose rows hold two UI5 date pickers BEFORE School (From Date required, To Date
# optional); the pickers' input lives in a shadow root; Enter in the box would submit (Save) the whole form.
DATES = """<html><body>
<script>
customElements.define('ui5-date-picker-xweb-calendar-widget', class extends HTMLElement {
  connectedCallback() { if (this.shadowRoot) return; const s = this.attachShadow({mode: 'open'}); const i = document.createElement('input'); i.placeholder = 'MM/DD/YYYY';
    i.addEventListener('keydown', e => { if (e.key === 'Enter') window.saved = 1; });
    i.addEventListener('change', () => this.setAttribute('value', i.value)); s.appendChild(i); this.style.display = 'inline-block'; }
});
</script>
<div class="rcmFormSection" id="132:section"><h3>Education (Optional if you uploaded a resume)</h3>
 __ROWS__
 <span>Add</span></div>
<div class="rcmFormSection" id="200:section"><label for="sig">Electronic Signature</label><input id="sig">
 <ui5-date-picker-xweb-calendar-widget accessible-name="Today's Date" format-pattern="MM/dd/yyyy"></ui5-date-picker-xweb-calendar-widget></div>
</body></html>"""
DROW = """<div class="row"><p>Row number {n}</p>
 <div><ui5-date-picker-xweb-calendar-widget accessible-name="From Date" format-pattern="MM/dd/yyyy" required value=""></ui5-date-picker-xweb-calendar-widget></div>
 <div><ui5-date-picker-xweb-calendar-widget accessible-name="To Date" format-pattern="MM/dd/yyyy" value=""></ui5-date-picker-xweb-calendar-widget></div>
 <label for="{a}:_txtFld">* School</label><input id="{a}:_txtFld" value="{school}">
 <label for="{b}:_txtFld">Degree</label><input id="{b}:_txtFld" value="{deg}"><span>Remove</span></div>"""
EDUS = [{'school': 'Lakeview University', 'short': 'LU', 'level': 'master', 'start': '2026-09', 'end': '2027-12', 'current': True},
        {'school': 'Prairie State College', 'short': 'PSC', 'level': 'bachelor', 'end': '2026-05'}]   # fictional; the second has no start on file


def main():
    fails, logs = 0, []
    log = logs.append
    def check(name, ok):
        nonlocal fails
        print(('PASS ' if ok else 'FAIL ') + name); fails += 0 if ok else 1
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as td:
        try: b = pw.chromium.launch(headless=True)
        except Exception: b = pw.chromium.launch(channel=os.environ.get('CX_CHANNEL', 'chrome'), headless=True)   # a separate headless instance, never the job Chrome
        page = b.new_page(); page.set_default_timeout(3000)
        page.set_content(JOB)
        try:
            page.locator('#apply').click(timeout=1500); covered = False
        except Exception:
            covered = True
        check('the chat iframe covers Apply before (the Danfoss timeout)', covered)
        n = S.hide_chat(page, log)
        check('hide_chat hides one widget', n == 1)
        check('cookie banner untouched', page.locator('#onetrust-banner-sdk').is_visible())
        check('click_apply clicks after hiding', S.click_apply(page) == '' and page.evaluate('window.clicked') == 1)

        prof = json.loads(json.dumps(jsa_profile.load())); prof['answers'].pop('profile_visibility', None)
        unset = os.path.join(td, 'unset.json'); json.dump(prof, open(unset, 'w'))
        prof['answers']['profile_visibility'] = VIS
        withv = os.path.join(td, 'set.json'); json.dump(prof, open(withv, 'w'))
        page.set_content(REG)
        check('privacy agreement link opened and accepted', S.accept_privacy(page, log))
        os.environ['JSA_PROFILE'] = unset; need = []
        ok = S.register_radios(page, log, need)
        check('no profile_visibility in config → needs-user', not ok and len(need) == 1 and 'Make My Profile Visible to' in need[0])
        check('nothing picked without an answer', not any(page.locator(f'#v{i}').is_checked() for i in (1, 2, 3)))
        os.environ['JSA_PROFILE'] = withv; need = []
        ok = S.register_radios(page, log, need)
        check('profile_visibility set → the worldwide option', ok and not need and page.locator('#v1').is_checked())

        # W — Newell: radios with no id / no label
        page.set_content(REG2); need = []
        g = [x for x in S.radio_texts(page.evaluate(S.REG_RADIOS)) if x['id'] == 'radio:fbclc_searPref']
        check('no-id radios: option texts from the surrounding DOM', bool(g) and g[0]['options'] == [O1, O2, O3])
        ok = S.register_radios(page, log, need)
        check('no-id radios: worldwide picked by name + value and read back', ok and not need and page.evaluate('window.vis') == '1'
              and page.locator('input[name=fbclc_searPref][value="1"]').is_checked() and any('read back' in x for x in logs))

        # X — Danfoss: one-page register-and-apply form
        page.set_content(DANFOSS)
        check('Danfoss page = register_apply (was: no sign-in box, no Create link → stop)', S.page_kind(S.page_sig(page)) == 'register_apply' and S.on_application(page))
        real_items = S.keychain_items
        S.keychain_items = lambda: [('jobagent-workday', 'Aa1!' + 'b' * 10), ('jobagent-workday-long', 'Cc2#' + 'd' * 16)]   # fictional passwords, never the Keychain
        try:
            done, rows = S.fill_account(page, log)
        finally:
            S.keychain_items = real_items
        check('terms of use accepted (hidden DPCS box + confirmation line)', S.is_accepted(page) and page.locator('#fbclc_dpcsId').input_value() == '12345')
        check('account boxes all read back', rows and all(r['ok'] for r in rows) and {'fbclc_pwd', 'fbclc_userName', 'fbclc_ituCode', 'fbclc_country'} <= {r['key'] for r in rows})
        check('password: the item that fits 18 characters, never in the rows', page.locator('#fbclc_pwd').input_value() == 'Aa1!' + 'b' * 10
              and not any('Aa1!' in json.dumps(r) for r in rows) and not any('Aa1!' in x for x in logs))
        check('job-alert box unticked, country code United States (+1)', not page.locator('#fbclc_emailEnabled').is_checked()
              and page.locator('#fbclc_ituCode').input_value() == 'US')
        cv = os.path.join(td, 'Resume_Test.pdf'); open(cv, 'wb').write(b'%PDF-1.4\n')
        check('CV uploaded and shown in its block', S.upload(page, 0, cv, log, 'Resume') and S.shown_file(page, 0) == 'Resume_Test.pdf')
        check('Apply not pressed by the fill', not page.evaluate('window.applied'))
        import presubmit as PS
        hard, _ = PS.audit({'fields': rows}, 'https://career2.successfactors.eu/careers?company=quintalsev')
        check('canon audit: account rows raise no block', not hard)

        # Y — Acuity: short inverted school names
        sys.path.insert(0, os.path.join(HERE, '..'))
        import sf_background as SB
        import sf_combo_edu as CE
        f = {'key': '323:_input', 'list': '324:_listSelect', 'label': 'College/University', 'type': 'combo', 'value': ''}
        for ent, want, q in (({'school': 'University of Chicago', 'short': 'UChicago'}, 'Chicago, U of', 'Chicago'),
                             ({'school': 'University of Illinois Urbana-Champaign', 'short': 'UIUC'}, 'Illinois, U of/ChUrb', 'Illinois')):
            page.set_content(COMBO); page.evaluate('(o) => { window.OPTS = o; }', ACUITY)
            got = SB.edu_school(page, f, ent, S.combo_options, S.N)
            ok = got == (want, q, 'match')
            if ok:
                CE.combo_pick(page, f, got[0], S.N, S.css, query=got[1])
            check(f'{ent["short"]}: searched {q!r}, picked {want!r}', ok and page.locator('[id="323:_input"]').input_value() == want)
        page.set_content(COMBO); page.evaluate('(o) => { window.OPTS = o; }', ['Illinois, U of', 'Illinois State U', 'Other'])
        got = SB.edu_school(page, f, {'school': 'University of Illinois Urbana-Champaign', 'short': 'UIUC'}, S.combo_options, S.N)
        check('campus-less "Illinois, U of" → ask Joey, never Other, box left empty', got == (None, None, 'ambiguous') and page.locator('[id="323:_input"]').input_value() == '')

        # AF — the final Apply under a fixed cookie banner
        page.set_viewport_size({'width': 1000, 'height': 600})
        page.set_content(COVERED)
        try:
            page.locator('#fbqa_apply').click(timeout=1500); covered = False
        except Exception:
            covered = True
        check('the cookie banner covers Apply before (the Danfoss timeout)', covered and not page.evaluate('window.applied'))
        clicked, why = S.press_apply(page, S.apply_button(page).first, log)
        check('press_apply: the page\'s own click landed once', clicked and page.evaluate('window.applied') == 1)
        check('cookie banner shown again and none of its buttons pressed', page.locator('.cookiemanager').is_visible() and page.evaluate('window.cookie') is None
              and page.evaluate("document.querySelector('.cookiemanager').getAttribute('style')").startswith('display:block'))
        page.set_content(COVERED_MODAL); page.evaluate('window.applied = undefined')    # set_content keeps the window object
        clicked, why = S.press_apply(page, S.apply_button(page).first, log)
        check('a session dialog over Apply → stop, not hidden, not clicked', not clicked and 'covered' in why and page.locator('#sessionTimeout').is_visible()
              and not page.evaluate('window.applied'))
        st, note = S.press_result(clicked, None, not S.apply_button(page).count())
        check('…and the outcome is blocked "Apply not pressed", never "pressed the final button"', st == 'blocked' and note.startswith('Apply not pressed')
              and 'pressed the final button' not in note)

        # AE — education From Date boxes
        page.set_viewport_size({'width': 1300, 'height': 900})
        rows_html = DROW.format(n=1, a=328, b=333, school='Lakeview University', deg="Master's Degree") + DROW.format(n=2, a=358, b=363, school='Prairie State College', deg="Bachelor's Degree")
        page.set_content(DATES.replace('__ROWS__', rows_html))
        typed = []
        real_set = S.date_set
        def spy(pg, f, v):
            typed.append((f['key'], v)); return real_set(pg, f, v)
        out, keys = CE.fill_combo_education(page, log, S.plan, S.READ, S.combo_options, S._open, S.css, S.N, edus=EDUS, date_set=spy)
        dates = {r['key']: r for r in out if r['type'] == 'date'}
        extra = {x['id'] for x in S.read_extra(page) if x['type'] == 'date'}
        check('row dates keyed like READ_EXTRA, the signature date not taken', set(dates) == {'ui5date:From Date', 'ui5date:To Date', 'ui5date:From Date#1', 'ui5date:To Date#1'}
              and set(dates) <= extra and "ui5date:Today's Date" not in keys and set(dates) <= keys)
        check('row 1 From Date typed 09/01/2026 and read back', typed == [('ui5date:From Date', '09/01/2026')] and S.date_value(page, dates['ui5date:From Date']) == '09/01/2026')
        check('Enter never pressed in a date box (it would Save the form)', not page.evaluate('window.saved'))
        check('row 2 (no start on file) → asks Joey, nothing typed', dates['ui5date:From Date#1'].get('ask', '').endswith('— Joey') and dates['ui5date:From Date#1']['want'] is None
              and S.date_value(page, dates['ui5date:From Date#1']) == '')
        check('optional To Date boxes left empty', dates['ui5date:To Date']['want'] is None and not dates['ui5date:To Date']['required'])
        b.close()
    print('\n'.join('  log: ' + x for x in logs))
    print('fails', fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
