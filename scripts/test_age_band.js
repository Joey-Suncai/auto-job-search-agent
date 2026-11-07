#!/usr/bin/env node
// Harness for answer_rules.js ageBand (rule 13): DeepSeek cases in test_cases/age_band_cases.json, verdicts in age_band_verdicts.json.
const fs = require('fs'), path = require('path');
const { ageBand } = require('../skills/auto-apply/scripts/answer_rules.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'age_band_cases.json'), 'utf8'));
const vp = path.join(__dirname, 'test_cases', 'age_band_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
let bad = 0;
for (const c of cases) {
  const got = ageBand(c.options, c.age);
  if (got !== c.expect && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', JSON.stringify(got), '| expect', JSON.stringify(c.expect), '| age', c.age, JSON.stringify(c.options)); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
