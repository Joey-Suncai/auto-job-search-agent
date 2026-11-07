// Harness for answer_rules the 2026-11-03 batch-5 answers (rule 13): DeepSeek cases, verdicts in answers_1103_verdicts.json.
const fs = require('fs'), path = require('path');
const { answerFor } = require(path.join(__dirname, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'answers_1103_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'answers_1103_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: c.type, o: c.options || [] });
  const got = a && (a.value !== undefined ? a.value : a);
  if (String(got) !== String(c.expect) && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', JSON.stringify(got), '| expect', c.expect, '|', c.label); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
