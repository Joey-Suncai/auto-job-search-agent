// JSA-376: "applied before" matches the tracker by the FULL company name (legal-form words aside), never by the core
// alone — "Prior Labs" must not hit an application to "Prior Technologies" (an invented "applied before: Yes").
// Cases: DeepSeek (scripts/test_cases/applied_core_cases.json, verdicts in applied_core_verdicts.json).
const path = require('path'), fs = require('fs');
const d = new Date(), today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const tracker = { date: today, rows: [] };
globalThis.__cxApplied = tracker;
const { answerFor } = require('../answer_rules.js');
const tc = path.join(__dirname, '..', '..', '..', '..', 'scripts', 'test_cases');
const vf = path.join(tc, 'applied_core_verdicts.json');
const verdicts = fs.existsSync(vf) ? JSON.parse(fs.readFileSync(vf)) : {};
let fail = 0;
const run = (name, company, rows, label, expect) => {
  tracker.rows = rows.map(c => ({ company: c, applied_on: '2026-10-01' }));
  const a = answerFor({ l: label.replace(/\b(Did you|Have you) (previously |ever )?apply\b/i, 'Have you previously applied').replace(/\bapply to\b/i, 'applied to'), t: 'select', o: ['Yes', 'No'] }, { company });
  const v = a.status === 'ok' ? String(a.value) : '';
  const got = a.rule !== 'applied_before' ? 'other' : a.status !== 'ok' ? 'ask' : /^yes/i.test(v) ? 'yes' : 'no';
  const ok = verdicts[name] ? got !== 'yes' : got === expect;
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + got + (ok ? '' : ' (want ' + expect + ')'));
};
for (const c of JSON.parse(fs.readFileSync(path.join(tc, 'applied_core_cases.json')))) run(c.name, c.company, c.tracker, c.label, c.expect);
run('Prior Labs vs Prior Technologies (JSA-376 re-review)', 'Prior Labs', ['Prior Technologies'], 'Have you previously applied to Prior Labs?', 'ask');
run('no ctx.company: own full name in the question', '', ['Prior Labs'], 'Have you previously applied to Prior Labs?', 'yes');
run('no ctx.company: look-alike only', '', ['Prior Technologies', 'Prior Labs'], 'Have you previously applied to Prior Labs?', 'yes');
run('"& Co." tracker name', 'Rosfensev', ['Rosfensev & Co.'], 'Have you previously applied to Rosfensev?', 'yes');
run('same name, Inc suffix', 'Acme', ['Acme, Inc.'], 'Have you previously applied to Acme?', 'yes');
console.log(fail ? `\n${fail} FAILED` : '\nALL PASS');
process.exit(fail ? 1 : 0);
