// Harness for answer_rules: immigration_status (F-1) vs auth_kind (CPT) on fill-ins (rule 13, JSA-287).
// DeepSeek cases: test_cases/imm_status_rule_cases.json (from imm_status_rule_spec.md); Claude's verdicts in
// imm_status_rule_verdicts.json. "neither" = the answer comes from neither of the two rules.
const fs = require('fs'), path = require('path');
const R = require(path.join(__dirname, '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_cases', 'imm_status_rule_cases.json'), 'utf8'));
const vp = path.join(__dirname, 'test_cases', 'imm_status_rule_verdicts.json');
const verdicts = fs.existsSync(vp) ? JSON.parse(fs.readFileSync(vp, 'utf8')) : {};
cases.push({ name: 'real_vanguard_2026_11_10', label: 'If no, please provide your immigration status in the U.S.', expect: 'immigration_status' });
let bad = 0;
for (const c of cases) {
  const a = R.answerFor({ label: c.label, type: 'textarea', options: [] }, {});
  const got = ['immigration_status', 'auth_kind'].includes(a.rule) ? a.rule : 'neither';
  const want = (verdicts[c.name] || {}).expect || c.expect;
  if (got !== want) { bad++; console.log('DISAGREE', c.name, '| got', got, `(${a.rule} = ${a.value})`, '| expect', want, '|', c.label); }
}
console.log(`${cases.length} cases · disagreements without a verdict: ${bad}`);
process.exit(bad ? 1 : 0);
