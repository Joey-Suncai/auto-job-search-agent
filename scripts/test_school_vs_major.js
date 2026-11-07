// Harness for answer_rules school / discipline / avail_season (rule 13): DeepSeek cases, Claude's verdicts in school_vs_major_verdicts.json
const fs = require('fs'), path = require('path');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'school_vs_major_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'school_vs_major_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: c.type, o: c.options || [] });
  if ((a.rule !== c.expect_rule || a.value !== c.expect_value) && !(c.name in verdicts)) { bad++;
    console.log('DISAGREE', c.name, '| got', a.rule, JSON.stringify(a.value), '| expect', c.expect_rule, JSON.stringify(c.expect_value), '|', c.label, c.type); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
