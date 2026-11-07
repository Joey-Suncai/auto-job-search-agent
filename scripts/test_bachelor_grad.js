// Harness for eligibility_rules BACHELORS_WORDING on graduation windows (rule 13): DeepSeek cases, verdicts in bachelor_grad_verdicts.json.
const fs = require('fs'), path = require('path');
const E = require(path.join(__dirname, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'eligibility_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'bachelor_grad_cases.json')));
const vp = path.join(__dirname, 'test_cases', 'bachelor_grad_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp)) : {};
const pad = ' Summer 2027 internship, 12 weeks, Chicago. ';
let bad = 0;
for (const c of cases) {
  const r = E.classify({ title: 'Data Analyst Intern', level: 'Internship', loc: 'Chicago, IL', text: pad.repeat(4) + c.text });
  const got = r.reasons.some(x => x.code === 'BACHELORS_WORDING' || x.code === 'UNDERGRAD_ONLY');
  if (got !== c.expect && !(c.name in verdicts)) { bad++; console.log('DISAGREE', c.name, '| got', got, '| expect', c.expect, '|', c.text.slice(0, 200), '|', r.reasons.map(x => x.code).join(',')); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
