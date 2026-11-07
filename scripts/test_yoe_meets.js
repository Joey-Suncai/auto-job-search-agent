// Harness for the JSA-105 rule yoe_meets + jdYears (rule 13): DeepSeek cases, verdicts in yoe_meets_verdicts.json.
// expect = the option text (answered Yes), "ASK" (handed to Joey: unknown with ask) or "NOT_THIS_RULE" (another rule / unknown, never yoe_meets).
const fs = require('fs'), path = require('path');
const { answerFor } = require(path.join(__dirname, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'yoe_meets_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'yoe_meets_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let bad = 0;
for (const c of cases) {
  const a = answerFor({ l: c.label, t: c.type, o: c.options || [] }, { jd: c.jd });
  const got = a.ask ? 'ASK' : a.rule !== 'yoe_meets' && c.expect === 'NOT_THIS_RULE' ? 'NOT_THIS_RULE' : a.status === 'ok' ? a.value : a.status + ':' + (a.why || '');
  if (String(got) !== String(c.expect) && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', JSON.stringify(got), '| expect', c.expect, '|', c.label, '| JD:', c.jd); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
