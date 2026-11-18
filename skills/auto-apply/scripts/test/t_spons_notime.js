// JSA-361 stop-gap (Joey 2026-11-16): a sponsorship question with no time word is never answered automatically — the
// rules return unknown + ask (no saved answer settles it). Cases: DeepSeek (scripts/test_cases/spons_notime_cases.json,
// verdicts in spons_notime_verdicts.json) + the real no-time questions of the forms corpus (2026-11-16).
const path = require('path'), fs = require('fs');
const { answerFor } = require('../answer_rules.js');
const tc = path.join(__dirname, '..', '..', '..', '..', 'scripts', 'test_cases');
const verdicts = fs.existsSync(path.join(tc, 'spons_notime_verdicts.json')) ? JSON.parse(fs.readFileSync(path.join(tc, 'spons_notime_verdicts.json'))) : {};
let fail = 0;
const check = (name, f, expect) => {
  const a = answerFor(f);
  const asked = a.status !== 'ok';
  const ok = expect === 'ask' ? asked && a.ask === true : !(a.ask && /no time word/.test(a.why || ''));
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + JSON.stringify(a.status === 'ok' ? a.value : a.status + ':' + (a.why || '')));
};
for (const c of JSON.parse(fs.readFileSync(path.join(tc, 'spons_notime_cases.json')))) {
  if (verdicts[c.name]) continue;
  check('case ' + c.name, { l: c.label, t: c.type || 'radio', o: c.options || [] }, c.expect);
}
const yn = ['Yes', 'No'];
const REAL_ASK = [   // forms corpus, 2026-11-16 (spons_future answered each before)
  'Do you require Visa sponsorship?',
  'Are you legally authorized to work in the US without sponsorship? ¿Está legalmente autorizado para trabajar en los Estados Unidos sin patrocinio?',
  'Are you legally authorized to work in the USA without sponsorship?',
  'Do you require immigration sponsorship to work for Affirm in the United States?',
  'Do you require sponsorship?',
  'Do you require visa sponsorship to work in the United States?',
  'Requesting visa sponsorship?',
  'Are you legally authorized to work in the country for this position without requiring employer-sponsored work authorization?',
  "If you answered 'No' to the previous question, will you require sponsorship for a work visa or other work authorization?",
  'Do you require employer-sponsored work authorization?',
  'Without sponsorship, are you legally permitted to work in the country where this job is located?',
  'Will you require visa sponsorship to work for Galostgal?',
];
for (const l of REAL_ASK) check('real no-time: ' + l.slice(0, 70), { l, t: 'radio', o: yn }, 'ask');
check('real no-time, sentence options', { l: 'Do you require visa sponsorship for employment in the USA?', t: 'select', o: ['Yes, I require sponsorship', 'No, I do not require sponsorship'] }, 'ask');
const REAL_KEEP = [
  'Will you now or in the future require sponsorship for employment visa status (e.g., H-1B visa status)?',
  'Will you now or ever require sponsorship to work in the United States?',
  'Do you currently require immigration sponsorship for work authorization?',
  'Will you require immigration sponsorship to begin working for GALLUMPELL?',
  'Would you need Versevfen to sponsor a visa for this internship?',
  'Are you legally authorized to work in the United States for the duration of this internship without sponsorship from the firm?',
  'Will you require immigration sponsorship within the next 3-7 years for work authorization? (for example: F1, H1B, H4)',
  'Will immigration sponsorship be required in the next 12 months?',
];
for (const l of REAL_KEEP) check('real with time word: ' + l.slice(0, 70), { l, t: 'radio', o: yn }, 'answer');
check('details box keeps its explanation', { l: 'Optional: If you answered Yes or Unsure, can you provide further details about the sponsorship you would need?', t: 'textarea', o: [] }, 'answer');
// review 2026-11-16: a time word in a note after the question, a detail word on a Yes/No control, a place word, petition wording
for (const l of ['Do you require sponsorship? Note: we do not currently sponsor visas.',
                 'Do you require visa sponsorship? (Please note that we are not able to sponsor at this time.)',
                 'Will you require sponsorship to work at our current office location?',
                 'Will you require sponsorship in the present role location?',
                 'Do you require visa sponsorship for this role? Today we sponsor H-1B.',
                 'Will you need Acme to file a petition for employment-based immigration status?',
                 'Do you require visa sponsorship? Please specify.',
                 'Do you require sponsorship (please provide details if yes)?'])
  check('review: ' + l.slice(0, 70), { l, t: 'radio', o: yn }, 'ask');
check('review: a detail box still keeps its handling', { l: 'If you require sponsorship, please provide details.', t: 'textarea', o: [] }, 'answer');
console.log(fail ? fail + ' FAILED' : 'ALL SPONS NO-TIME TESTS PASS'); process.exit(fail ? 1 : 0);
