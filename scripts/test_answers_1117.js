// JSA-410: Joey's 2026-11-17 answers (Akuna course, visitor visa, fall enrollment, relocation cities, recorded video, EEO furnish) and the
// C9 facts (current education level, school, high school, US state). Cases: DeepSeek (scripts/test_cases/answers_1117_cases.json; spec + format
// beside it; verdicts in answers_1117_verdicts.json) + the real form questions (fields corpus 2026-10/11).
process.env.JSA_TODAY = '2026-11-17';   // enrolled_fall depends on today's date
const path = require('path'), fs = require('fs');
const { answerFor } = require('../skills/auto-apply/scripts/answer_rules.js');
const tc = path.join(__dirname, 'test_cases');
const vp = path.join(tc, 'answers_1117_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
let fail = 0;
const check = (name, c) => {
  const o = c.options || [];
  const a = answerFor({ l: c.label, t: c.type || (o.length ? 'select' : 'text'), o });
  const ok = c.expect === 'ask' ? a.status !== 'ok' && (!c.rule || a.rule === c.rule) : a.status === 'ok' && (String(c.expect).startsWith('re:') ? new RegExp(c.expect.slice(3)).test(a.value) : a.value === c.expect);   // 're:…' = a pattern (the user's own facts are not written in the repo)
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + JSON.stringify(a.status === 'ok' ? a.value + ' [' + a.rule + ']' : a.status + ':' + (a.why || '')));
};
for (const c of JSON.parse(fs.readFileSync(path.join(tc, 'answers_1117_cases.json')))) if (!verdicts[c.name]) check('case ' + c.name, c);
const CITIES = ['Chicago', 'New York', 'London', 'Bristol', 'Amsterdam', 'Paris', 'Singapore', 'Shanghai', 'Hong Kong', 'Mumbai', 'Sydney'];
check('real: Akuna Options 101', { label: 'Did you complete our online Options 101 Course? If not, head to quindelmor.teachable.com for more information on this free course that is open to all!', options: ["Not yet!", "I'm >50% through the online Options 101 course", 'I have concluded the online Options 101 course'], expect: 'Not yet!' });
check('real: Visitor Visa', { label: 'Visitor Visa', options: ['Yes', 'No'], expect: 'No' });
check('real: Hunt fall semester (derived, no options)', { label: "Hunt's internship program concludes at the end of summer. Will you be enrolled in the fall semester following the internship?", type: 'multi', expect: 'Yes' });
check('real: Jump other relocation cities', { label: 'Other than the location posted for this role, please indicate which other locations you are interested in relocating to:', type: 'multi', options: CITIES, expect: 'Chicago | New York | Shanghai | Hong Kong' });
check('real: no qualifying city → ask', { label: 'Other than the location posted for this role, please indicate which other locations you are interested in relocating to:', type: 'multi', options: ['London', 'Paris', 'Singapore'], expect: 'ask' });
check('real: recorded video (file)', { label: 'Record a 1-minute video telling us about the time you most successfully hacked into a (non-computer) system', type: 'file', expect: 'ask', rule: 'video_record' });
check('real: Loom link', { label: 'Please share a Loom link introducing yourself', type: 'text', expect: 'ask', rule: 'video_record' });
check('real: portfolio / video resume URL stays a URL', { label: 'Portfolio/video resume URL', type: 'text', expect: 're:^https://github\\.com/' });
check('real: EEO furnish', { label: 'Do you wish to furnish this information?', options: ['No', 'Yes'], expect: 'Yes' });
check('real: current education level', { label: 'What is your current education level?', options: ['High School', 'Undergraduate', "Master's", 'PhD', 'JD', 'MD', 'Other'], expect: "Master's" });
check('real: highest education stays the completed one', { label: 'What is your highest level of education?', type: 'select', options: ["Bachelor's", "Master's"], expect: "Bachelor's" });
check('real: college/university text (Talkelsev)', { label: 'Enter your college/university', expect: 're:^University of ' });
check('real: High School text (Talkelsev)', { label: 'High School', expect: 're:High School$' });
check('real: which US state (Nevharpell)', { label: 'If applicable, which US state do you reside in?', options: ['Alabama', 'Illinois', 'Indiana'], expect: 'Illinois' });
check('review: share-information consent is not EEO furnish', { label: 'Do you wish to share this information with third parties?', options: ['Yes', 'No'], expect: 'ask' });
check('review: an academic course is not the Akuna course', { label: 'Have you taken the Data Structures course?', options: ['Yes', 'No'], expect: 'ask' });
check('review: Cambridge, UK is not picked', { label: 'Other than the location posted for this role, please indicate which other locations you are interested in relocating to:', type: 'multi', options: ['Cambridge, UK', 'Greenwich, UK', 'Boston, MA', 'Shanghai'], expect: 'Boston, MA | Shanghai' });
check('review: video logistics yes/no is not the recorded-video rule', { label: 'Are you comfortable with a video interview?', options: ['Yes', 'No'], expect: 'ask' });
check('review: state if outside the US asks', { label: 'What state do you live in if outside the US?', type: 'text', expect: 'ask' });
for (const q of ['Year you expect to begin full time employment', 'Recruiting Timelines', 'Extra']) check('no fact → ask: ' + q, { label: q, expect: 'ask' });
console.log(fail ? 'FAILED ' + fail : 'ALL PASS'); process.exit(fail ? 1 : 0);
