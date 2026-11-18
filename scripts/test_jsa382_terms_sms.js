// JSA-382 (rule 13): DeepSeek-written cases (test_cases/jsa382_terms_sms_cases.json, spec jsa382_terms_sms_spec.md); Claude's
// verdicts on disagreements in jsa382_terms_sms_verdicts.json (each cites its source). One combined "terms + SMS" checkbox is
// always Yes (Joey 2026-11-17); an SMS-only box keeps the sms rule; a terms-only box is never the combined rule.
const fs = require('fs'), path = require('path');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const dir = path.join(__dirname, 'test_cases');
const cases = JSON.parse(fs.readFileSync(path.join(dir, 'jsa382_terms_sms_cases.json'))).concat(JSON.parse(fs.readFileSync(path.join(dir, 'jsa382_review_cases.json'))));   // + the reviewer's false-positive probes
const vp = path.join(dir, 'jsa382_terms_sms_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: 'checkbox', o: [] }, { company: '' });
  const problems = [];
  if (c.expect_rule && a.rule !== c.expect_rule) problems.push(`rule ${a.rule} != ${c.expect_rule}`);
  if (c.expect_rule_not && a.rule === c.expect_rule_not) problems.push(`rule is ${a.rule}`);
  if (c.expect_rule && c.expect === 'Yes' && !(a.status === 'ok' && a.value === 'Yes')) problems.push(`answer ${a.status}/${a.value}`);
  if (problems.length && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '|', problems.join('; '), '|', c.label.slice(0, 100)); }
}
console.log(`JSA-382: ${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
