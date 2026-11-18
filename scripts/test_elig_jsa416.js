// JSA-416 (queue.md 2026-11-17): the gate must read the internship's cycle and the degree already held.
//   A. internship whose stated terms / dates are all before Summer 2027 → PAST_CYCLE (Fundwell, DoorDash)
//   B. postdoc title or a completed PhD required → POSTDOC_OR_PHD_DONE (NTT Data)
// Cases: three real ones + DeepSeek variants from the spec (test_elig_jsa416_cases.json, ds_testgen.py, judged by Claude).
const path = require('path');
const E = require(path.join(__dirname, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'eligibility_rules.js'));
const pad = ' Lorem ipsum dolor sit amet. '.repeat(10);
const real = [
  ['Fundwell: June – August 2026', { title: 'AI Innovation Internship', level: 'Internship', loc: 'New York, NY',
    text: pad + "About the role: Duration: June – August 2026 (3 months). Full-time, paid. Master's students welcome." + pad }, 'Ineligible', 'PAST_CYCLE'],
  ['DoorDash: Summer 2026 / Fall 2026 cohorts', { title: 'AI Research Fellowship Intern', level: 'Internship', loc: 'San Francisco, CA',
    text: pad + "Please select which cohort start date you would be available for: Summer 2026 (June start date) / Fall 2026 (September start date). Master's students welcome." + pad }, 'Ineligible', 'PAST_CYCLE'],
  ['NTT Data: postdoc, PhD completed before start', { title: 'Postdoctoral AI Scientist', level: 'Internship', loc: 'San Jose, CA',
    text: pad + "PhD in Computer Science … The PhD must be completed prior to the start of the appointment. 12–24 month postdoctoral appointment." + pad }, 'Ineligible', 'POSTDOC_OR_PHD_DONE'],
  ['PhD required for another role ok', { title: 'Data Intern - Summer 2027', level: 'Internship', loc: 'Chicago, IL', text: pad + "Interns need a Master's. A PhD is required for the Senior Scientist role. Your mentor must have a PhD." + pad }, 'Eligible', null],
  ['past program mention, no term ok-not-block', { title: 'Data Intern', level: 'Internship', loc: 'Chicago, IL', text: pad + "Our Summer 2026 internship program was a success. Master's students welcome." + pad }, 'Eligible', null],
  ['Summer 2027 ok', { title: 'Data Intern - Summer 2027', level: 'Internship', loc: 'Chicago, IL', text: pad + "Duration: June – August 2027. Master's students welcome." + pad }, 'Eligible', null],
  ['PhD preferred ok', { title: 'Research Intern', level: 'Internship', loc: 'Chicago, IL', text: pad + "Summer 2027. A PhD is preferred but not required. Master's students welcome." + pad }, 'Eligible', null],
  ['posted fall 2026, starts summer 2027 ok', { title: 'ML Intern', level: 'Internship', loc: 'Chicago, IL', text: pad + "Posted Fall 2026. The internship starts in Summer 2027 (June – August 2027). Master's students welcome." + pad }, 'Eligible', null],
];
let bad = 0;
const run = (n, j, exp, code) => { const r = E.classify(j); const codes = r.reasons.map(x => x.code);
  const ok = r.verdict === exp && (!code || [].concat(code).some(k => codes.includes(k))); if (!ok) bad++;
  console.log((ok ? 'ok  ' : 'FAIL') + ' ' + n + ' -> ' + r.verdict + ' ' + codes.join(',')); };
for (const [n, j, exp, code] of real) run(n, j, exp, code);
for (const c of require('./test_elig_jsa416_cases.json')) {
  if (c.ambiguous || c.skip) continue;
  // an Ineligible case must be blocked by one of the cycle / doctorate / off-cycle codes, not by an unrelated rule
  run('ds: ' + c.name, { title: c.title, level: c.level, loc: c.loc, text: c.text }, c.expect, c.expect === 'Ineligible' ? ['PAST_CYCLE', 'POSTDOC_OR_PHD_DONE', 'OFF_CYCLE'] : null);
}
console.log('fails', bad); if (bad) process.exitCode = 1;
