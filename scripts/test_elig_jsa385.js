// JSA-385 (Joey 2026-11-17): internship + "no sponsorship" is Eligible. Cases use real JD wording from the store.
//   (1) employer only says it does not sponsor → code NO_SPONSORSHIP_INTERN   (ranked a little lower by the sponsor factor)
//   (2) candidate must not need sponsorship now or in the future → NO_FUTURE_SPONSORSHIP_INTERN (one tier lower)
//   student / temporary visa named as not accepted, any-employer, permanent authorization, citizen / clearance → unchanged
const path = require('path');
const E = require(path.join(__dirname, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'eligibility_rules.js'));
const pad = ' Lorem ipsum dolor sit amet. '.repeat(10);
const mk = (t, title) => ({ title: title || 'Data Analyst Intern - Summer 2027', level: 'Internship', loc: 'Chicago, IL',
  text: pad + "Summer 2027. Master's students welcome. " + t + pad });
const cases = [
  // [name, text, verdict, code that must be present ('' = none of the two), code that must be absent]
  ['1 unable to sponsor', 'We are unable to sponsor visas for this role.', 'Eligible', 'NO_SPONSORSHIP_INTERN'],
  ['1 not eligible for visa sponsorship (Nissan-like)', 'Visa Sponsorship: Not Available.', 'Eligible', 'NO_SPONSORSHIP_INTERN'],
  ['1 no sponsorship for this program', 'Note that there is no sponsorship for this program.', 'Eligible', 'NO_SPONSORSHIP_INTERN'],
  ['1 does not sponsor work visas (Ingredion half)', 'The company does not sponsor employment visas for this position.', 'Eligible', 'NO_SPONSORSHIP_INTERN'],
  ['2 BNY: not require sponsorship now or in the future', 'Does not require sponsorship for employment visa status (now or in the future) in the country where applying.', 'Eligible', 'NO_FUTURE_SPONSORSHIP_INTERN'],
  ['2 Brunswick: not eligible for sponsorship now or in the future', 'This position is not eligible for employment visa sponsorship now or in the future.', 'Eligible', 'NO_FUTURE_SPONSORSHIP_INTERN'],
  ['2 without current or future sponsorship', 'Candidates must be authorized to legally work in the United States without current or future sponsorship.', 'Eligible', 'NO_FUTURE_SPONSORSHIP_INTERN'],
  ['2 authorized and not require sponsorship now or in the future', 'Must be legally authorized to work in the U.S. and not require sponsorship now or in the future.', 'Eligible', 'NO_FUTURE_SPONSORSHIP_INTERN'],
  ['2 unsure (no time word, candidate side) → 2', 'Must be authorized to work in the United States without sponsorship.', 'Eligible', 'NO_FUTURE_SPONSORSHIP_INTERN'],
  ['2 do not need sponsorship (no time word) → 2', 'Open to candidates who do not need visa sponsorship.', 'Eligible', 'NO_FUTURE_SPONSORSHIP_INTERN'],
  // unchanged blocks / reviews
  ['F-1/CPT named as refused still blocks (Viget)', 'We are unable to sponsor or take over sponsorship for any type of employment visa, including F-1 (OPT/CPT).', 'Ineligible', null],
  ['any employer still blocks (Western)', 'Applicants must be authorized to work for any employer in the U.S. We are unable to sponsor or take over sponsorship of an employment visa at this time.', 'Ineligible', null],
  ['unrestricted work authorization still blocks (Mohawk)', 'Position requires unrestricted work authorization in the United States; work/visa sponsorship for this position is not available.', 'Ineligible', null],
  ['temporary visas not eligible → review, not eligible', 'We do not provide visa sponsorship. Individuals with temporary visas or who need sponsorship now or in the future are not eligible for hire at this time.', 'Review', null],
  ['CPT/OPT do not meet the requirements → review', 'We do not provide visa sponsorship. Candidates on CPT, OPT, or STEM OPT usually require future sponsorship for long term employment and do not meet the requirements for this program.', 'Review', null],
  ['plain refusal + international students ineligible → review', 'We do not provide visa sponsorship. International students are not eligible.', 'Review', null],
  ['future wording + clearance eligibility → review', 'Must not require sponsorship now or in the future. Eligibility for clearance required.', 'Review', null],
  ['citizen still blocks', 'We cannot sponsor visas. Must be a U.S. citizen or permanent resident.', 'Ineligible'],
  ['clearance still blocks', 'Must be able to obtain a security clearance. Applicants must not require sponsorship.', 'Ineligible'],
  ['full-time + no sponsorship still blocks', 'We are unable to sponsor visas for this role.', 'Ineligible', null, { title: 'Data Analyst', level: 'New grad' }],
  ['sponsorship offered → plus only, no no-sponsor code', 'We will sponsor H-1B visas for qualified candidates.', 'Eligible', null],
];
E.setCandidate({ needs_sponsorship: true, citizen_or_pr: false, grad: '2027-12', degree_level: 'masters' });
let bad = 0;
for (const [name, text, verdict, code, over] of cases) {
  const j = Object.assign(mk(text), over || {});
  if (over && over.level === 'New grad') j.title = 'Data Analyst';
  const r = E.classify(j), codes = r.reasons.map(x => x.code);
  const two = ['NO_SPONSORSHIP_INTERN', 'NO_FUTURE_SPONSORSHIP_INTERN'].filter(c => codes.includes(c) && r.reasons.find(x => x.code === c).level === 'plus');
  let ok = r.verdict === verdict;
  if (verdict === 'Ineligible') {} else if (code) ok = ok && two.length === 1 && two[0] === code; else ok = ok && two.length === 0;
  if (!ok) { bad++; console.log('FAIL', name, '| got', r.verdict, r.reasons.map(x => x.code + ':' + x.level).join(','), '| expect', verdict, code); }
  else console.log('ok  ', name);
}
console.log(`${cases.length} cases · fails ${bad}`);
process.exit(bad ? 1 : 0);
