#!/usr/bin/env node
// JSA-324 (Dell 11-11, Joey 「只答问你自己的题」): the on-site rule answers only questions about HIM being on site.
// DeepSeek-written cases (rule 13): test_cases/onsite_subject_cases.json; judged disagreements in
// test_cases/onsite_subject_verdicts.json. true → an on-site-family rule answers; false → never the on-site rule.
const fs = require('fs'), path = require('path');
const { answerFor } = require(path.join(__dirname, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js'));
let cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'onsite_subject_cases.json'), 'utf8'));
cases = cases.cases || cases;
const vp = path.join(__dirname, 'test_cases', 'onsite_subject_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
const FAMILY = /^(onsite|relocate|commute|local_area|hybrid|in_person|travel)$/;
let fails = 0;
cases.forEach((c, i) => {
  const r = answerFor({ l: c.question, t: 'select', o: ['Yes', 'No'] });
  const got = c.expect ? (r.status === 'ok' && FAMILY.test(r.rule || '')) : r.rule !== 'onsite';
  if (!got) {
    if (verdicts[i]) console.log(`JUDGED ${i}: ${verdicts[i]}`);
    else { fails++; console.log(`FAIL ${i} expect ${c.expect}: rule ${r.rule || r.status} — ${c.question}`); }
  }
});
console.log(`onsite subject: ${cases.length - fails}/${cases.length} agree (or judged)`);
process.exit(fails ? 1 : 0);
