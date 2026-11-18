// JSA-408 (learn d083be64): an exclusion note ("Do not include VISA or relocation expectations") is not part of the question —
// the accommodations question answers No, not the relocate rule's Yes. Cases: DeepSeek (scripts/test_cases/exclusion_note_cases.json;
// spec + format beside it; verdicts in exclusion_note_verdicts.json) + the real MW question (2026-10-31).
const path = require('path'), fs = require('fs');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const tc = path.join(__dirname, 'test_cases');
const vp = path.join(tc, 'exclusion_note_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let fail = 0;
const check = (name, c) => {
  const a = answerFor({ l: c.label, t: c.type || 'select', o: c.options || ['Yes', 'No'] });
  const ok = c.expect === 'ask' ? a.status !== 'ok' : a.status === 'ok' && a.value === c.expect;
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + JSON.stringify(a.status === 'ok' ? a.value + ' [' + a.rule + ']' : a.status + ':' + (a.why || '')));
};
for (const c of JSON.parse(fs.readFileSync(path.join(tc, 'exclusion_note_cases.json')))) if (!verdicts[c.name]) check('case ' + c.name, c);
check('real: MW accommodations with exclusion note (10-31)', { label: 'Do you require any reasonable adjustments or accommodations to participate in the recruitment process? (i.e extra time on tests, wheelchair access in office etc. Do not include VISA or relocation expectations)', expect: 'No' });
check('real: relocation still Yes', { label: 'Are you willing to relocate for this role?', expect: 'Yes' });
check('exclusion note on another rule: relocation question that excludes visa stays Yes', { label: 'Are you willing to relocate? (Do not include visa sponsorship)', expect: 'Yes' });
{ const a = answerFor({ l: 'If you heard about Radix from an employee here (other than our recruiters), please enter their name', t: 'text' });   // "other than …" is the subject, not an exclusion note: it must not turn into his own name
  const ok = a.status !== 'ok'; if (!ok) fail++; console.log((ok ? 'PASS ' : 'FAIL ') + '"(other than our recruiters)" stays in the question (Radix 11-05) -> ' + JSON.stringify(a.value ?? a.status)); }
console.log(fail ? 'FAILED ' + fail : 'ALL PASS'); process.exit(fail ? 1 : 0);
