// Harness for answer_rules yes/no option mapping (rule 13): DeepSeek-written cases, Claude's verdicts in yes_no_options_verdicts.json
const fs = require('fs'), path = require('path');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'yes_no_options_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'yes_no_options_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: 'combo', o: c.options });
  const got = a.status === 'ok' && a.value ? a.value : 'unknown';
  if (got !== c.expect && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', JSON.stringify(got), '| expect', JSON.stringify(c.expect), '|', c.label, JSON.stringify(c.options)); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
