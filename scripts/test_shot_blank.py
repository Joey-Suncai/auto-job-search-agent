#!/usr/bin/env python3
"""Harness for confirm_page.shot_blank (rule 13, JSA-223): DeepSeek cases from test_cases/shot_blank_spec.md, images drawn
here; verdicts in test_cases/shot_blank_verdicts.json. Needs Pillow (venv python); skipped without it."""
import io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import confirm_page as CP  # noqa: E402
try:
    from PIL import Image, ImageDraw
except ImportError:
    print('SKIP test_shot_blank: Pillow not installed (run with ~/.job-agent-venv/bin/python)'); sys.exit(0)
cases = json.load(open(os.path.join(HERE, 'test_cases', 'shot_blank_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'shot_blank_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    if 'image' in c:
        im = c['image']; img = Image.new('RGB', (im['w'], im['h']), tuple(im['bg'])); d = ImageDraw.Draw(img)
        for m in im.get('marks') or []:
            d.rectangle([m['x'], m['y'], m['x'] + m['w'] - 1, m['y'] + m['h'] - 1], fill=tuple(m['color']))
        buf = io.BytesIO(); img.save(buf, 'PNG'); data = buf.getvalue()
    else:
        data = (c.get('raw') or '').encode()
    got = CP.shot_blank(data)
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
# QUINMORHAR 11-05: white page with one 130x2 link underline
img = Image.new('RGB', (2940, 1602), (255, 255, 255)); ImageDraw.Draw(img).rectangle([730, 520, 859, 521], fill=(40, 90, 200))
buf = io.BytesIO(); img.save(buf, 'PNG')
if not CP.shot_blank(buf.getvalue()):
    bad += 1; print('DISAGREE drw_underline_only')
# a page that paints its thank-you text 2.5 s late: confirmation_shot waits for the text and the file is not blank
try:
    from playwright.sync_api import sync_playwright
    import tempfile
    with sync_playwright() as pw:
        br = None
        for kw in ({'channel': 'chrome', 'headless': True}, {'headless': True}):
            try:
                br = pw.chromium.launch(**kw); break
            except Exception:
                continue
        if br is not None:
            page = br.new_page(viewport={'width': 900, 'height': 600})
            page.set_content('<body style="font-size:40px"><div id=t style="visibility:hidden">Thank you for applying! Your application has been submitted.</div>'
                             '<script>setTimeout(()=>{t.style.visibility="visible"},2500)</script></body>')
            path = os.path.join(tempfile.mkdtemp(), 'shot.png'); logs = []
            ok = CP.confirmation_shot(page, path, logs.append)
            if not ok or CP.shot_blank(open(path, 'rb').read()):
                bad += 1; print('DISAGREE late-painted page', ok, logs)
            page.close()
            if CP.confirmation_shot(page, os.path.join(tempfile.mkdtemp(), 'y.png'), logs.append) is not False:
                bad += 1; print('DISAGREE closed page must return False without raising')
            br.close()
except ImportError:
    pass
print(f'{len(cases)} cases + QUINMORHAR shape · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
