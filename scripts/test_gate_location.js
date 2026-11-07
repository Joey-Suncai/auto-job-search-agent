// Harness: the gate's locationVerdict (eligibility_rules.js) on the shared non-U.S. location cases (rule 13, JSA-084):
// DeepSeek cases in us_location_cases.json (same spec as us_location.py), verdicts in gate_location_verdicts.json.
const fs = require('fs'), path = require('path');
const E = require(path.join(__dirname, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'eligibility_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'us_location_cases.json'), 'utf8'));
const vp = path.join(__dirname, 'test_cases', 'gate_location_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
let bad = 0;
for (const c of cases) {
  const got = !!E.locationVerdict(c.location);
  if (got !== c.expect && !verdicts[c.name]) { bad++; console.log('DISAGREE', c.name, '| got', got, '| expect', c.expect, '|', JSON.stringify(c.location)); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
