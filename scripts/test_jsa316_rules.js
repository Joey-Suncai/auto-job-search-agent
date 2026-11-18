// Harness for the JSA-316 government vs defense-support rules (rule 13): DeepSeek-written cases (test_cases/jsa316_rules_cases.json, spec
// jsa316_rules_spec.md), Claude's verdicts on the disagreements in jsa316_rules_verdicts.json. The tracker is a
// fixture written here with dates relative to today (Acme Corp 30 days ago, Globex Inc 400 days ago).
const fs = require('fs'), path = require('path'), os = require('os');
const day = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); };
const fx = path.join(os.tmpdir(), `jsa316_applied_${process.pid}.jsonl`);
fs.writeFileSync(fx, [{ company: 'Acme Corp', applied_on: day(30) }, { company: 'Globex Inc', applied_on: day(400) }].map(r => JSON.stringify(r)).join('\n') + '\n');
process.env.JSA_APPLIED = fx;
// the spec's one saved answer (Joey 2026-11-11, data home qa) on top of whatever profile the run uses (release tests: the repo's)
const base = require('../config/profile.js');
const px = path.join(os.tmpdir(), `jsa316_profile_${process.pid}.json`);
fs.writeFileSync(px, JSON.stringify(Object.assign({}, base, { qa: (base.qa || []).concat([{ q: 'Are there any reasons why you would not be able to fully contribute in support of the U.S. military and allied forces?',
  match: '/(any )?reasons? (why )?you (would|could) not (be able to )?(fully )?(contribute|support|work).{0,80}(military|defen[cs]e|armed forces|allied forces)/i', pick: ['/^Yes$/i'], text: 'Yes' }]) })));
delete require.cache[require.resolve('../config/profile.js')];
process.env.JSA_PROFILE = px;
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
fs.unlinkSync(px);
fs.unlinkSync(fx);
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'jsa316_rules_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'jsa316_rules_verdicts.json');
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
