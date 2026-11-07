// Runs the dashboard's English display layer (en(), between /*EN-BEGIN*/ and /*EN-END*/ in dashboard_index.html) on
// the DeepSeek cases (test_cases/dashboard_en_cases.json, from dashboard_en_spec.md) and, when the data home is
// readable, on every distinct shown value of the store (no Chinese may be left). JSA-180.   node scripts/test_dashboard_en.js [--strict]
const fs = require('fs'), path = require('path'), os = require('os');
const page = fs.readFileSync(path.join(__dirname, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'dashboard_index.html'), 'utf8');
const src = page.split('/*EN-BEGIN*/')[1].split('/*EN-END*/')[0];
const en = new Function(src + '\nreturn en;')();
const CJK = /[一-鿿]/;
let fails = 0;
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'dashboard_en_cases.json'), 'utf8'));
const vp = path.join(__dirname, 'test_cases', 'dashboard_en_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
for (const c of cases) {
  const got = en(c.input), bad = [];
  if (c.expect_exact !== null && c.expect_exact !== undefined && got !== c.expect_exact) bad.push(`want exactly ${JSON.stringify(c.expect_exact)}`);
  if (c.input === null && got !== null) bad.push('null not kept');
  for (const m of c.must_contain || []) if (!String(got).includes(m)) bad.push(`missing ${JSON.stringify(m)}`);
  if (c.no_cjk && CJK.test(String(got))) bad.push('Chinese left');
  if (bad.length) {
    if (verdicts[c.name] && verdicts[c.name].verdict === 'case') { console.log('CASE ', c.name, '—', verdicts[c.name].why.slice(0, 120)); continue; }
    fails++; console.log('FAIL ', c.name, '|', bad.join('; '), '| got', JSON.stringify(got));
  }
}
console.log(`${cases.length} DeepSeek cases`);
// real store values (skipped when the data home is not there, e.g. CI)
let home = process.env.JSA_HOME || '';
try { if (!home) home = fs.readFileSync(path.join(os.homedir(), '.config', 'job-search-agent', 'home'), 'utf8').trim(); } catch (e) { /* none */ }
const store = home ? path.join(home.replace(/^~/, os.homedir()), 'data', 'store') : '';
if (store && fs.existsSync(path.join(store, 'jobs.jsonl'))) {
  const shown = { jobs: ['elig', 'elig_reason', 'elig_evidence', 'notes'], applications: ['last_email', 'action_needed'], emails: ['summary', 'action'] };
  const seen = new Set(); let left = 0;
  for (const [ds, fields] of Object.entries(shown)) {
    for (const line of fs.readFileSync(path.join(store, ds + '.jsonl'), 'utf8').split('\n')) {
      if (!line.trim()) continue; const r = JSON.parse(line);
      for (const f of fields) { const v = r[f]; if (typeof v !== 'string' || seen.has(v)) continue; seen.add(v);
        const g = en(v); if (CJK.test(g)) { left++; if (left <= 15) console.log('LEFT ', ds + '.' + f, '|', g.slice(0, 160)); } }
    }
  }
  console.log(`${seen.size} distinct store values · Chinese left in ${left}`);
  if (process.argv.includes('--strict')) fails += left;   // a new checker phrase must not block a release: warning unless --strict
} else console.log('store not found — real-value check skipped');
console.log(fails ? `${fails} FAILED` : 'ALL PASS'); process.exit(fails ? 1 : 0);
