// Harness for the phone_device answer (JSA-185, rule 13): DeepSeek cases from phone_device_spec.md, verdicts in phone_device_verdicts.json.
const fs = require('fs'), path = require('path');
const { answerFor } = require(path.join(__dirname, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'phone_device_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'phone_device_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: c.type, o: c.options || [] });
  const got = !a || a.status === 'unknown' ? 'UNKNOWN' : a.value;
  if (String(got) !== String(c.expect) && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', JSON.stringify(got), '| expect', c.expect, '|', c.label, JSON.stringify(c.options)); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
