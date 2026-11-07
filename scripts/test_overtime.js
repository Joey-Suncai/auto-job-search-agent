// Harness for the answer_rules.js `overtime` rule (rule 13): DeepSeek cases, verdicts in overtime_verdicts.json.
const fs = require('fs'), path = require('path');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'overtime_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'overtime_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: c.type, o: c.options || [] });
  const isOt = a.rule === 'overtime' || a.id === 'overtime' || /overtime/.test(JSON.stringify(a.why || ''));
  const got = c.expect === 'NOT_OVERTIME' ? (a.value === 'Evenings only' || a.value === 'Just evenings' ? 'OVERTIME?' : 'NOT_OVERTIME') : a.value;
  if (got !== c.expect && !verdicts[c.name]) { bad++; console.log('DISAGREE', c.name, '| got', JSON.stringify(a.value ?? a.status), '| expect', c.expect, '|', c.label, c.options); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
