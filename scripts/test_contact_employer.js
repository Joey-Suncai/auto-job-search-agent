// JSA-409 (learn 2ed24953): "If you are currently employed, may we contact your employer?" → N/A (he has no current job), never Yes.
// Cases: DeepSeek (scripts/test_cases/contact_employer_cases.json; spec + format beside it; verdicts in contact_employer_verdicts.json) + the real forms.
const path = require('path'), fs = require('fs');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const tc = path.join(__dirname, 'test_cases');
const vp = path.join(tc, 'contact_employer_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let fail = 0;
const check = (name, c) => {
  const a = answerFor({ l: c.label, t: c.type || (c.options && c.options.length ? 'select' : 'text'), o: c.options || [] });
  const ok = c.expect === 'ask' ? a.status !== 'ok' : a.status === 'ok' && a.value === c.expect;
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + JSON.stringify(a.status === 'ok' ? a.value + ' [' + a.rule + ']' : a.status + ':' + (a.why || '')));
};
for (const c of JSON.parse(fs.readFileSync(path.join(tc, 'contact_employer_cases.json')))) if (!verdicts[c.name]) check('case ' + c.name, c);
const Q = 'If you are currently employed, may we contact your employer?';
check('real: conditional text box (11-17 proposal)', { label: Q, expect: 'N/A' });
check('real: conditional with N/A option', { label: Q, options: ['Yes', 'No', 'N/A'], expect: 'N/A' });
check('real: conditional with Yes/No only → ask', { label: Q, options: ['Yes', 'No'], expect: 'ask' });
check('real: EMC unconditional stays Yes (Joey 11-01)', { label: 'May we contact your current employer?', options: ['Yes', 'No'], expect: 'Yes' });
for (const q of ['If employed, may we contact your employer?', 'If you are employed, may we contact your current employer?', 'Are you currently employed? If so, may we contact your employer?', 'Are you currently employed by a competitor? If so, may we contact your employer to verify?']) {   // review: these phrasings fell through to contact_employer → Yes
  check('phrasing: ' + q, { label: q, expect: 'N/A' });
  check('phrasing with N/A option: ' + q, { label: q, options: ['Yes', 'No', 'Not employed'], expect: 'Not employed' });
}
check('previous employers stay Yes', { label: 'May we contact your previous employers?', options: ['Yes', 'No'], expect: 'Yes' });
console.log(fail ? 'FAILED ' + fail : 'ALL PASS'); process.exit(fail ? 1 : 0);
