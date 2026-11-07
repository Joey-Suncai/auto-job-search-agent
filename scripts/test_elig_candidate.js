// Harness for eligibility_rules.setCandidate (rule 13, JSA-081): DeepSeek cases, verdicts in elig_candidate_verdicts.json.
const fs = require('fs'), path = require('path');
const E = require(path.join(__dirname, '..', 'skills', 'job-hunt-pipeline', 'scripts', 'eligibility_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'elig_candidate_cases.json'), 'utf8'));
const vp = path.join(__dirname, 'test_cases', 'elig_candidate_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
let bad = 0;
for (const c of cases) {
  E.setCandidate({ needs_sponsorship: true, citizen_or_pr: false, grad: '2027-12', degree_level: 'masters' }); E.setCandidate(c.candidate);
  const r = E.classify({ title: c.title, text: c.text, loc: c.loc, level: c.level });
  if (r.verdict !== c.expect && !verdicts[c.name]) { bad++; console.log('DISAGREE', c.name, '| got', r.verdict, r.reasons.map(x => x.code + ':' + x.level).join(','), '| expect', c.expect); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
