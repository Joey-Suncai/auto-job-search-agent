#!/usr/bin/env node
// JSA-325 (Dell / Excellus 11-11, Joey 「是非问句不填名称 + major 加词边界」): ynQuestion + the name rules standing aside.
// DeepSeek-written cases (rule 13): test_cases/yn_question_cases.json; judged disagreements: yn_question_verdicts.json.
const fs = require('fs'), path = require('path');
const AR = require(path.join(__dirname, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js'));
let cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'yn_question_cases.json'), 'utf8'));
cases = cases.cases || cases;
const vp = path.join(__dirname, 'test_cases', 'yn_question_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
let fails = 0;
cases.forEach((c, i) => {
  const got = AR.ynQuestion(c.question);
  if (got !== c.expect) {
    if (verdicts[i]) console.log(`JUDGED ${i}: ${verdicts[i]}`);
    else { fails++; console.log(`FAIL ${i} expect ${c.expect} got ${got} — ${c.question}`); }
  }
});
// the two 11-11 cases end to end, and the name rules still filling plain value boxes
const fx = [
  ['Is your current employer a reseller of Vernevlum (including Dell, Dell EMC and affiliated companies), products, services or technologies? (if yes, please note Dell may contact your current employer should you accept an offer of employment)?', r => r.rule !== 'employer'],
  ['While typically the majority of work can be completed remotely, there are requirements for all interns to attend weekly, in-person, workshops. Are you able to provide your own means of transportation to attend these workshops?', r => r.rule !== 'discipline'],
  ['The majority of our interns are based in Chicago.', r => r.rule !== 'discipline'],
  ['What is your major?', r => r.rule === 'discipline'], ['Major', r => r.rule === 'discipline'],
  ['What is your current employer?', r => r.rule === 'employer'], ['School', r => r.rule === 'school'],
  ['Are you currently employed? If so, what is your current employer?', r => r.rule === 'employer'],
];
for (const [l, ok] of fx) {
  const r = AR.answerFor({ l, t: 'text', o: [] });
  if (!ok(r)) { fails++; console.log(`FAIL fixture: rule ${r.rule || r.status} — ${l.slice(0, 80)}`); }
}
console.log(`yn question: ${cases.length} DeepSeek cases + ${fx.length} fixtures, fails ${fails}`);
process.exit(fails ? 1 : 0);
