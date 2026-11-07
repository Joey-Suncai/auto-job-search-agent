#!/usr/bin/env node
// Harness for the age_range question pattern in answer_rules.js (rule 13, JSA-213): DeepSeek cases in
// test_cases/age_question_cases.json (written for age 23), Claude's verdicts in age_question_verdicts.json.
const fs = require('fs'), path = require('path');
const prof = JSON.parse(JSON.stringify(require('../config/profile.js')));
prof.answers.age_range = { age: 23, as_of: new Date().toISOString().slice(0, 10) };   // the cases assume age 23
globalThis.__cxProfile = prof;
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'age_question_cases.json'), 'utf8'));
const vp = path.join(__dirname, 'test_cases', 'age_question_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: 'select', o: c.options });
  const isAge = a.rule === 'age_range' || /^age_range:/.test(a.why || '');
  const got = isAge && a.status === 'ok' ? a.value : '';
  const ok = isAge === c.is_age_band && (!c.is_age_band || got === c.expect);
  if (!ok && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| label', JSON.stringify(c.label), '| got', isAge, JSON.stringify(got), '| expect', c.is_age_band, JSON.stringify(c.expect)); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
