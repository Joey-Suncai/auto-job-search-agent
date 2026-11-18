#!/usr/bin/env python3
"""Generate the offline mock forms for t_run.sh from app_fake/plan.json (single source).

  python3 test/make_mock.py [plan.json]

Writes test/mock_fake.html, test/mock_captcha.html, and the two gate fixtures
test/app_bad/plan.json (a planned field missing from the page) and
test/app_notready/plan.json (needs_user not resolved -> plan.ready false).
The mock is plain DOM (no React): run.py's script fill and verify.js L1/L3 are
what these tests cover; the React L2 layer is covered by t_verify.js.
"""
import copy, json, os, sys, html

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('MOCK_OUT') or HERE   # t_run.sh writes into its temp dir, never the tracked fixtures (JSA-289)
PLAN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'app_fake', 'plan.json')


def esc(x):
    return html.escape(str(x if x is not None else ''))


def field_html(f):
    key = f['key']
    if f.get('status') != 'ok' or key in ('latitude', 'longitude'):
        return ''
    typ = f.get('type')
    lab = esc(f.get('label') or key)
    fid = f['sel'].lstrip('#') if f['sel'].startswith('#') else key
    req = ' required' if f.get('required') else ''
    ans = esc(f.get('answer'))
    if typ in ('combo', 'multi') or key == 'country':
        opts = list(dict.fromkeys([str(o) for o in (f.get('options') or [])] + [str(f.get('answer'))]))
        body = '<option value="">-- select --</option>' + ''.join(
            '<option value="%s">%s</option>' % (esc(o), esc(o)) for o in opts)
        return '<div class="field"><label for="%s">%s</label>' % (esc(fid), lab) + \
               '<select id="%s" name="%s" data-type="combo"%s>%s</select></div>' % (esc(fid), esc(key), req, body)
    if typ == 'textarea':
        return '<div class="field"><label for="%s">%s</label><textarea id="%s" name="%s"%s></textarea></div>' % (
            esc(fid), lab, esc(fid), esc(key), req)
    if typ == 'checkbox':
        return '<div class="field"><label><input type="checkbox" id="%s" name="%s"> %s</label></div>' % (
            esc(fid), esc(key), lab)
    on_input = ''
    if key == 'location':          # a real location widget also sets the hidden lat/long
        on_input = ' oninput="document.getElementsByName(\'latitude\')[0].value=\'41.88\';document.getElementsByName(\'longitude\')[0].value=\'-87.63\'"'
    return '<div class="field"><label for="%s">%s</label><input type="text" id="%s" name="%s"%s%s></div>' % (
        esc(fid), lab, esc(fid), esc(key), req, on_input)


REFUSE_JS = """
  var w = document.querySelector('form .field');            // Greenhouse-style client-side validation (Viking 10-31):
  var p = document.createElement('p');                       // the form stays, an error appears under a field, nothing is sent
  p.className = 'helper-text helper-text--error'; p.textContent = 'This field is required.';
  w.appendChild(p);
"""
THANKS_JS = """
  document.body.innerHTML = '<h2>Thank you for applying. Your application has been submitted.</h2>';
"""


def page(plan, captcha=False, extra='', refuse=False):
    fields = '\n'.join(x for x in (field_html(f) for f in plan['fields']) if x)
    cap = '<div class="h-captcha">protected by hCaptcha</div>\n' if captcha else ''
    return """<!doctype html><meta charset="utf-8"><title>mock</title>
<body>
<h1>Apply</h1>
<form id="app">
%s
%s
<input type="hidden" name="latitude" id="lat" value="">
<input type="hidden" name="longitude" id="lon" value="">
<button type="submit">Submit application</button>
</form>
%s
<script>
document.getElementById('app').addEventListener('submit', function (e) {
  e.preventDefault();%s});
</script>
</body>
""" % (fields, extra, cap, REFUSE_JS if refuse else THANKS_JS)


def main():
    plan = json.load(open(PLAN, encoding='utf-8'))
    open(os.path.join(OUT, 'mock_fake.html'), 'w', encoding='utf-8').write(page(plan))
    open(os.path.join(OUT, 'mock_captcha.html'), 'w', encoding='utf-8').write(page(plan, captcha=True))
    open(os.path.join(OUT, 'mock_refused.html'), 'w', encoding='utf-8').write(page(plan, refuse=True))   # JSA-209

    # a wrong answer that verify.js cannot see (the plan has no such field): only the canonical audit catches it
    bogus = ('<div class="field"><label for="degree">Degree</label>'
             '<select id="degree" name="degree" data-type="combo">'
             '<option value="">-- select --</option>'
             '<option value="Masters of Technology" selected>Masters of Technology</option>'
             '<option value="Master of Science">Master of Science</option></select></div>')
    open(os.path.join(OUT, 'mock_badanswer.html'), 'w', encoding='utf-8').write(page(plan, extra=bogus))

    bad = copy.deepcopy(plan)
    bad['folder'] = 'app_bad'
    target = next(f for f in bad['fields'] if f.get('status') == 'ok' and f.get('required'))
    target['sel'] = '#this_field_is_not_on_the_page'      # form changed since the plan was built
    os.makedirs(os.path.join(OUT, 'app_bad'), exist_ok=True)
    json.dump(bad, open(os.path.join(OUT, 'app_bad', 'plan.json'), 'w', encoding='utf-8'), indent=1)

    notready = copy.deepcopy(plan)
    notready['folder'] = 'app_notready'
    notready['ready'] = False
    notready['needs_user'] = [{'key': 'question_69874419', 'label': 'ZIP', 'reason': 'test: no rule'}]
    os.makedirs(os.path.join(OUT, 'app_notready'), exist_ok=True)
    json.dump(notready, open(os.path.join(OUT, 'app_notready', 'plan.json'), 'w', encoding='utf-8'), indent=1)
    print('mocks written: mock_fake.html, mock_captcha.html, mock_refused.html, mock_badanswer.html, app_bad/plan.json, app_notready/plan.json')


if __name__ == '__main__':
    main()