// Form replay (JSA-188): answers many stored forms in ONE node process with the current answer rules.
//   echo '{"forms": [{"id": "...", "company": "...", "fields": [{key, label, type, options}]}]}' | node replay_bridge.js [answer_rules.js]
//   → {"<form id>": {"<key>": answerFor result}}
// Same answering path as the runners: runner/rules_bridge.js answerAll (numbering stripped, yes/no-on-text-box guard, …).
const path = require('path');
const rulesPath = process.argv[2] || path.join(__dirname, '..', '..', 'skills', 'auto-apply', 'scripts', 'answer_rules.js');
const { answerFor } = require(path.resolve(rulesPath));
const { answerAll } = require(path.join(__dirname, '..', '..', 'skills', 'auto-apply', 'runner', 'rules_bridge.js'));
let s = '';
process.stdin.on('data', d => s += d).on('end', () => {
  const q = JSON.parse(s), out = {};
  for (const f of q.forms || []) {
    try { out[f.id] = answerAll(answerFor, f.fields || [], { jd: '', company: f.company || '' }); }
    catch (e) { out[f.id] = { __error: String(e && e.message || e) }; }
  }
  process.stdout.write(JSON.stringify(out));
});
