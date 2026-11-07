// Harness for eligibility_rules NO_SPONSORSHIP (rule 13): DeepSeek cases, Claude's verdicts in sponsorship_label_verdicts.json.
const fs = require('fs'), path = require('path');
const E = require(path.join(__dirname, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'eligibility_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'sponsorship_label_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'sponsorship_label_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
const pad = ' Full-time role starting January 2028. Master\'s students welcome. ';
let bad = 0;
for (const c of cases) {
  // a full-time role: since JSA-238 an internship with a plain no-sponsorship statement carries no NO_SPONSORSHIP code (CPT),
  // so pattern detection is tested where the code still shows
  const r = E.classify({ title: 'Data Analyst', level: 'New grad', loc: 'Chicago, IL', text: pad.repeat(4) + c.text });
  const got = r.reasons.some(x => x.code === 'NO_SPONSORSHIP');
  if (got !== c.expect && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', got, '| expect', c.expect, '|', c.text.slice(0, 200), '|', r.reasons.map(x => x.code).join(',')); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
