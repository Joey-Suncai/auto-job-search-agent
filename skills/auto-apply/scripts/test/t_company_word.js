// JSA-336 stop-gap (Joey approved the queue 2026-11-16): a word in the hiring company's name never decides the answer.
// "Have you ever worked at Pellwyndel …?" was answered Yes from the tracker (APPLIED_Q read "ever … Applied"), then
// "If yes, please enter your Pellwyndel email address" got his personal e-mail (AMAT dry runs 2026-11-12).
// Cases: DeepSeek (scripts/test_cases/company_word_cases.json, verdicts in company_word_verdicts.json) + real questions of
// the forms corpus (2026-11-16).
const path = require('path'), fs = require('fs');
// a fictional, dated tracker (never the live one): the AMAT error needs an earlier Pellwyndel application; "Applied
// Labs" / "Prior Technologies" have one-word cores that must not mask the plain words (review 2026-11-16)
const d = new Date(), today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
globalThis.__cxApplied = { date: today, rows: [{ company: 'Pellwyndel', applied_on: '2026-10-30' }, { company: 'Google', applied_on: '2026-10-01' },
  { company: 'Applied Labs', applied_on: '2026-10-02' }, { company: 'Prior Technologies', applied_on: '2026-10-03' }] };
const { answerFor } = require('../answer_rules.js');
const P = require('../../../../config/profile.js');
const tc = path.join(__dirname, '..', '..', '..', '..', 'scripts', 'test_cases');
const verdicts = fs.existsSync(path.join(tc, 'company_word_verdicts.json')) ? JSON.parse(fs.readFileSync(path.join(tc, 'company_word_verdicts.json'))) : {};
const EMPS = P.employers || [], MAIL = String((P.contact || {}).email || '').toLowerCase();
const sub = s => String(s || '').replace(/RESUME_EMPLOYER_A/g, EMPS[0] || 'RESUME_EMPLOYER_A').replace(/RESUME_EMPLOYER_B/g, EMPS[1] || EMPS[0] || 'RESUME_EMPLOYER_B');
const isNo = v => /^no\b/i.test(String(v || '').trim()) || /\b(never|have not|haven't)\b/i.test(String(v || ''));
const isYes = v => /^yes\b/i.test(String(v || '').trim());
let fail = 0;
const check = (name, f, ctx, expect) => {
  const a = answerFor(f, ctx);
  const v = a.status === 'ok' ? String(a.value || '') : '';
  let ok;
  if (expect === 'employment_no') ok = a.status === 'ok' && a.rule !== 'applied_before' && isNo(v);
  else if (expect === 'employment_yes') ok = a.status === 'ok' && a.rule !== 'applied_before' && isYes(v);
  else if (expect === 'applied') ok = a.rule === 'applied_before';
  else if (expect === 'not_filled') ok = (a.status !== 'ok' || a.leave || !v) && !(v && v.toLowerCase() === MAIL) && (!/e-?mail/i.test(f.l) || a.no_auto === true);
  else if (expect === 'personal_email') ok = a.status === 'ok' && v.toLowerCase() === MAIL;
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + JSON.stringify(a.status === 'ok' ? (a.rule + ': ' + v) : a.status + ':' + (a.why || '')));
};
for (const c of JSON.parse(fs.readFileSync(path.join(tc, 'company_word_cases.json')))) {
  if (verdicts[c.name]) {   // a verdict allows ask / another rule — never a worked-at Yes, never the tracker, never his e-mail
    const a = answerFor({ l: sub(c.label), t: c.type || 'radio', o: (c.options || []).map(sub), r: !!c.required }, { company: c.company });
    const v = a.status === 'ok' ? String(a.value || '') : '';
    const ok = !(c.expect === 'employment_no' && (isYes(v) || a.rule === 'applied_before')) && v.toLowerCase() !== MAIL;
    if (!ok) fail++;
    console.log((ok ? 'PASS ' : 'FAIL ') + 'verdict ' + c.name + ' -> ' + JSON.stringify(a.status === 'ok' ? a.rule + ': ' + v : a.status));
    continue;
  }
  check('case ' + c.name, { l: sub(c.label), t: c.type || 'radio', o: (c.options || []).map(sub), r: !!c.required }, { company: c.company }, c.expect);
}
const yn = ['Yes', 'No'];
const AMAT = 'Pellwyndel';
// the two AMAT dry runs (2026-11-12_Applied_Materials_*), with and without ctx.company
for (const ctx of [{ company: AMAT }, {}]) {
  const k = ctx.company ? ' (ctx.company)' : ' (no ctx.company)';
  check('real AMAT worked-at' + k, { l: 'Have you ever worked at Pellwyndel as a regular employee, contingent worker, intern, etc.?', t: 'select', o: yn, r: true }, ctx, 'employment_no');
  check('real AMAT email follow-up' + k, { l: 'If yes, please enter your Pellwyndel email address:', t: 'text', o: [] }, ctx, 'not_filled');
  check('real AMAT applied-before still the tracker' + k, { l: 'Have you previously applied to Pellwyndel?', t: 'select', o: yn }, ctx, 'applied');
}
// forms corpus 2026-11-16: worked-at questions (all answered No on submitted forms)
const REAL_NO = [
  ['Danfoss', 'Have you ever worked for Danfoss before?'],
  ['Everpure', 'Have you previously worked for Everpure (formerly Morostlum)?'],
  ['Fensevpell', 'Have you ever worked as an employee for Fensevpell, or any other Fensevpell Legal Entity?'],
  ['Harwynpell', 'Have you ever worked for Harwynpell or one if its subsidiary Companies?'],
  ['Osttalnev', 'Have you ever worked for Osttalnev before, as an employee or a contractor/consultant?'],
  ['Veeam', 'Have you previously worked for Veeam (including as a contractor or intern)? Current Veeam employees are required to apply through the Internal Job Board.'],
  ['QUINSEVFEN', "Have You Been Previously Employed By QUINSEVFEN? (If you're a current QUINSEVFEN employee, please do NOT use this application process. Apply through the QUINSEVFEN internal website.)"],
  ['Copart', 'Have you previously been employed by Copart or its subsidiaries? CURRENT EMPLOYEES: Please apply via your internal Workday account.'],
  ['Central Hudson', 'Have you previously been employed by Central Hudson? CURRENT EMPLOYEES: Please apply via your internal Workday account instead.'],
];
for (const [company, l] of REAL_NO) check('real worked-at: ' + l.slice(0, 60), { l, t: 'select', o: yn, r: true }, { company }, 'employment_no');
check('real applied-before (Sevnevfen 11-10)', { l: 'Have you previously applied to work at Sevnevfen?', t: 'select', o: yn }, { company: 'Sevnevfen' }, 'applied');
// review 2026-11-16: the hiring company in lower case; one-word tracker cores never mask a real applying question
check('lower-case hiring company', { l: 'have you ever worked at pellwyndel as a regular employee?', t: 'select', o: yn }, { company: AMAT }, 'employment_no');
check('title-case applying question, "Applied Labs" in the tracker', { l: 'Have You Previously Applied To Google?', t: 'select', o: yn }, { company: 'Google' }, 'applied');
check('"Prior to this" applying question, "Prior Technologies" in the tracker', { l: 'Prior to this, have you applied to Google?', t: 'select', o: yn }, { company: 'Google' }, 'applied');
check('hiring company "Prior Labs" (one-word core): still the applying rule — which tracker row matches is not checked here', { l: 'Prior to today, have you ever applied to Prior Labs?', t: 'select', o: yn }, { company: 'Prior Labs' }, 'applied');
check('plain e-mail stays his address', { l: 'Email Address', t: 'text', o: [] }, { company: AMAT }, 'personal_email');
console.log(fail ? `\n${fail} FAILED` : '\nALL PASS');
process.exit(fail ? 1 : 0);
