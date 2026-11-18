// Harness for the answer rules on optional education / name questions (rule 13, JSA-075): DeepSeek cases in
// test_cases/optional_facts_cases.json, verdicts in optional_facts_verdicts.json. A free-text box (no options) → which
// rule answers it: discipline / degree / grad_date / preferred_name, or null (no fact → left blank).
const fs = require('fs'), path = require('path');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'optional_facts_cases.json'), 'utf8'));
const vp = path.join(__dirname, 'test_cases', 'optional_facts_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
const FACTS = ['discipline', 'degree', 'grad_date', 'preferred_name'];
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: 'textarea' });
  const rule = a.rule === 'degree_full' ? 'degree' : a.rule;   // degree_full = the degree rule's full name for a typed "which degree are you pursuing" (JSA-296)
  const got = a.status === 'ok' && FACTS.includes(rule) ? rule : null;
  if (got !== c.expect && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', got, `(${a.rule || a.status})`, '| expect', c.expect, '|', c.label); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
