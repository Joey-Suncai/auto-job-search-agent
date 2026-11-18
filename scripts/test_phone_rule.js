// Harness for the answer_rules.js `phone` rule (JSA-315, rule 13): DeepSeek cases from test_cases/phone_rule_spec.md,
// Claude's verdicts on disagreements in phone_rule_verdicts.json. got = the number when the phone rule wrote it, else NOT_PHONE.
const fs = require('fs'), path = require('path');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'phone_rule_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'phone_rule_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: c.type || 'text', o: c.options || [] });
  const got = a.status === 'ok' && a.rule === 'phone' ? String(a.value) : 'NOT_PHONE';
  const want = c.expect === 'NOT_PHONE' ? 'NOT_PHONE' : String(c.expect);
  if (got !== want && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', got, `(${a.rule || a.status})`, '| expect', want, '|', c.label.slice(0, 120), JSON.stringify(c.options || [])); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
