// Harness for the JSA-291 status-list fix (rule 13): DeepSeek-written cases (test_cases/jsa291_rules_cases.json, spec
// jsa291_rules_spec.md), Claude's verdicts on any disagreement in jsa291_rules_verdicts.json (none needed: the one
// disagreement, "permanently authorized?" → Yes, was a code bug, fixed in the any_employer pattern).
const fs = require('fs'), path = require('path'), os = require('os');
const day = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); };
const fx = path.join(os.tmpdir(), `jsa281_applied_${process.pid}.jsonl`);
fs.writeFileSync(fx, [{ company: 'Acme Corp', applied_on: day(30) }, { company: 'Globex Inc', applied_on: day(400) }].map(r => JSON.stringify(r)).join('\n') + '\n');
process.env.JSA_APPLIED = fx;
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
fs.unlinkSync(fx);
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'jsa291_rules_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'jsa291_rules_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const opts = c.options || [];
  const a = answerFor({ l: c.label, t: opts.length ? 'combo' : 'text', o: opts }, { company: c.company || '' });
  const got = a.status === 'ok' ? (a.leave ? 'empty' : String(a.value)) : 'unknown';
  if (got !== c.expect && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', JSON.stringify(got), `(${a.rule || a.why || ''})`, '| expect', JSON.stringify(c.expect), '|', c.label.slice(0, 120), JSON.stringify(opts).slice(0, 80)); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
