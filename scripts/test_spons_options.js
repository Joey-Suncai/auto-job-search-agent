// JSA-407: sponsorship questions whose Yes options are split by time (now / in the future) pick the FUTURE one.
// Cases: DeepSeek (scripts/test_cases/spons_options_cases.json; spec + format beside it) + the real Nevbrakel question.
const path = require('path'), fs = require('fs');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const tc = path.join(__dirname, 'test_cases');
const vp = path.join(tc, 'spons_options_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let fail = 0;
const check = (name, c) => {
  const a = answerFor({ l: c.label, t: c.type || 'radio', o: c.options || [] });
  const ok = c.expect === 'ask' ? a.status !== 'ok' : a.status === 'ok' && a.value === c.expect;
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + JSON.stringify(a.status === 'ok' ? a.value : a.status + ':' + (a.why || '')));
};
for (const c of JSON.parse(fs.readFileSync(path.join(tc, 'spons_options_cases.json')))) if (!verdicts[c.name]) check('case ' + c.name, c);
const TOGETHER = ['Yes, I will require immigration sponsorship now to legally work in the country where the job is located.', 'Yes, I will require immigration sponsorship in the future to legally work in the country where the job is located.', 'No, I do not and will not require immigration sponsorship to legally work in the country where the job is located.'];
const Q = 'Will you now or in the future require company sponsorship to retain or extend your work authorization in the country where the job is located?';
check('real: Nevbrakel 3-option (10-31)', { label: Q, type: 'select', options: TOGETHER, expect: TOGETHER[1] });
check('real: Nevbrakel, options reordered', { label: Q, type: 'select', options: [TOGETHER[2], TOGETHER[1], TOGETHER[0]], expect: TOGETHER[1] });
check('real: Nevharpell now-or-future pair stays Yes', { label: 'Will you now or in the future require employer sponsorship for work authorization in this country? If you will be working under a student visa for this role, please select "Yes."', type: 'select', options: ['No, I will not require sponsorship now or in the future to work in this country', 'Yes, I will require sponsorship now or in the future to work in this country'], expect: 'Yes, I will require sponsorship now or in the future to work in this country' });
check('two Yes options, none future-only → ask', { label: Q, type: 'select', options: ['Yes, I will require sponsorship now', 'Yes, I will require sponsorship in my first year', 'No'], expect: 'ask' });
check('lone Yes-now option under a now-or-future question → ask', { label: Q, type: 'select', options: ['Yes, I require sponsorship now', 'No, I do not require sponsorship'], expect: 'ask' });
// Workday-style Zekelman wording (options not stored offline; shape assumed): the future option
check('Zekelman-style 3 options → future', { label: 'Will you now or in the future require sponsorship for employment authorization (i.e. H-1B, OPT, CPT, J-2, L-2, etc)?', type: 'select', options: ['Yes, I currently require employer sponsorship.', 'Yes, I will require employer sponsorship in the future.', 'No, I do not require employer sponsorship.'], expect: 'Yes, I will require employer sponsorship in the future.' });
console.log(fail ? 'FAILED ' + fail : 'ALL PASS'); process.exit(fail ? 1 : 0);
