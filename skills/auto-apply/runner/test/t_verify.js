// Deliberate-error tests for verify.js on a React + react-select mock of the Galtalnev Greenhouse form.
// run: node test/t_verify.js   (uses test/app_galtalnev/plan.json and the committed test/mock_bundle.js)
// Offline (JSA-006): no npm install. Playwright = Node's own if installed, else the copy bundled inside the job-agent
// venv's Python playwright (same browsers). mock_bundle.js = mock_app.jsx + React/react-select, rebuilt by build_mock_bundle.sh.
const fs = require('fs'), path = require('path'), os = require('os');
function loadPlaywright() {
  try { return require('playwright'); } catch (e) { /* fall through */ }
  const cands = [process.env.PLAYWRIGHT_NODE_PACKAGE].filter(Boolean);
  const lib = path.join(os.homedir(), '.job-agent-venv', 'lib');
  if (fs.existsSync(lib)) for (const py of fs.readdirSync(lib)) cands.push(path.join(lib, py, 'site-packages', 'playwright', 'driver', 'package'));
  for (const c of cands) if (fs.existsSync(path.join(c, 'index.js'))) return require(c);
  throw new Error('no playwright: npm i playwright, or set PLAYWRIGHT_NODE_PACKAGE to <python site-packages>/playwright/driver/package');
}
const { chromium } = loadPlaywright();
const D = __dirname;
const PLAN_P = path.join(D, 'app_galtalnev/plan.json');
if (!fs.existsSync(PLAN_P))   // the fixture is committed; rebuild it offline from the saved Greenhouse JSON if it is missing
  require('child_process').execFileSync('python3', [path.join(D, '../plan_build.py'), path.join(D, 'app_galtalnev'), '--gh-json',
    path.join(D, 'gh_galtalnev.json'), '--url', 'https://job-boards.greenhouse.io/galtalnev/jobs/0'], { stdio: 'inherit' });
const plan = JSON.parse(fs.readFileSync(PLAN_P));
const VERIFY = fs.readFileSync(path.join(D, '../verify.js'), 'utf8');
const pageFields = plan.fields.filter(f => f.status === 'ok').map(f => ({ key: f.key, label: f.label, required: f.required,
  id: f.sel.replace(/^#/, ''), type: (f.type === 'combo' || f.key === 'location') ? 'combo' : f.type, options: f.options || [] }));
const html = `<!doctype html><meta charset=utf-8><body><div id=root></div><script>window.__PLAN=${JSON.stringify(pageFields)}</script><script src="mock_bundle.js"></script>`;
fs.writeFileSync(path.join(D, 'mock.html'), html);

async function fillAll(page, skip = new Set(), override = {}) {
  for (const f of plan.fields) {
    if (f.status !== 'ok' || skip.has(f.key)) continue;
    const want = override[f.key] ?? f.answer;
    const isCombo = f.type === 'combo' || f.key === 'location';
    if (isCombo) {
      await page.click(f.sel); await page.keyboard.type(f.key === 'location' ? 'Chicago, Ill' : want);
      await page.waitForSelector('.select__option', { timeout: 2000 });
      const opts = await page.$$eval('.select__option', ns => ns.map(n => n.textContent));
      const i = opts.indexOf(f.key === 'location' ? want : want);
      if (i < 0) throw new Error('option not found ' + f.key + ' ' + want + ' in ' + opts);
      for (let k = 0; k < i; k++) await page.keyboard.press('ArrowDown');
      await page.keyboard.press('Enter');
    } else {
      await page.fill(f.sel, String(want));
    }
  }
  await page.mouse.click(5, 5);
}

let fails = 0;
function expect(name, r, check) {
  const ok = check(r);
  if (!ok) fails++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' → pass=' + r.pass + ' bad=' + JSON.stringify(r.bad.map(b => b.key + ':' + b.layer)) + ' errors=' + JSON.stringify(r.errors.map(e => e.key.slice(0, 30))));
}

(async () => {
  const br = await chromium.launch({}).catch(() => chromium.launch(Object.assign({}, {}, { channel: 'chrome' })))  /* no downloaded browser → the installed Google Chrome */;
  const ctx = await br.newContext();
  const fresh = async () => { const p = await ctx.newPage(); await p.goto('file://' + path.join(D, 'mock.html')); await p.waitForSelector('#first_name'); return p; };
  const evalVerify = async p => p.evaluate(({ src, plan }) => { eval(src); return __cxVerify(plan); }, { src: VERIFY, plan });
  const scenario = async (name, fn, check) => { const p = await fresh(); await fn(p); const r = await evalVerify(p); expect(name, r, check); await p.close(); };

  await scenario('0 all correct (phone shown formatted, country shown as +1)', p => fillAll(p), r => r.pass && r.counts.l2_ok > 20);
  await scenario('1 wrong option picked (Fall instead of Summer)', p => fillAll(p, new Set(), { question_69874408: 'Fall (September - December)' }),
    r => !r.pass && r.bad.some(b => b.key === 'question_69874408' && b.layer === 'L1'));
  await scenario('2 required text left empty + blur shows error', async p => { await fillAll(p, new Set(['question_69874419'])); await p.focus('#question_69874419'); await p.mouse.click(5, 5); },
    r => !r.pass && r.bad.some(b => b.key === 'question_69874419') && r.errors.length >= 1);
  await scenario('3 DOM-only value (browser_fill style: React state not updated)', async p => {
      await fillAll(p, new Set(['first_name']));
      await p.evaluate(() => { const el = document.getElementById('first_name'); el.setAttribute('value', 'Alex'); el.value = 'Alex'; });
    }, r => !r.pass && r.bad.some(b => b.key === 'first_name' && b.layer === 'L2'));
  await scenario('4 react-select typed but not selected ("No" left in the search box)', async p => {
      await fillAll(p, new Set(['question_69874411'])); await p.click('#question_69874411'); await p.keyboard.type('No'); await p.mouse.click(5, 5);
    }, r => !r.pass && r.bad.some(b => b.key === 'question_69874411'));
  await scenario('5 location typed but no suggestion chosen (hidden latitude empty)', async p => {
      await fillAll(p, new Set(['location'])); await p.click('#candidate-location'); await p.keyboard.type('Chicago'); await p.mouse.click(5, 5);
    }, r => !r.pass && r.bad.some(b => b.key === 'location') && r.errors.some(e => e.key === 'latitude'));
  await scenario('6 value wiped by a re-render after DOM-only fill', async p => {
      await fillAll(p, new Set(['email']));
      await p.evaluate(() => { document.getElementById('email').value = 'alex.rivera@example.com'; window.__rerender(); });
      await p.waitForTimeout(100);
    }, r => !r.pass && r.bad.some(b => b.key === 'email'));
  await scenario('7 wrong text (preferred name Joey instead of plan value)', p => fillAll(p, new Set(), { question_69874412: 'Joey' }),
    r => !r.pass && r.bad.some(b => b.key === 'question_69874412' && b.layer === 'L1'));
  await br.close();
  console.log(fails ? fails + ' FAILED' : 'ALL VERIFY TESTS PASS');
  process.exit(fails ? 1 : 0);
})();
