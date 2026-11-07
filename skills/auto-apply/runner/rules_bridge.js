// Answers a list of plan fields with the standard rules (skills/auto-apply/scripts/answer_rules.js — the single source).
// Node:    echo '[{key,label,type,options}]' | node rules_bridge.js <answer_rules.js>   → {key: answerFor result}
//          or echo '{"fields": [...], "jd": "<JD text>", "company": "<hiring company>"}' — rules with jd: true answer from the JD
//          (JSA-105); referral questions check the company against the referrer pool (JSA-195) — no company = they are asked
// Browser: plan_build.py evaluates this file + answer_rules.js and calls answerAll(answerFor, list) (Macs without Node).
function answerAll(answerFor, list, ctx) {
  const P = globalThis.__cxProfile || (typeof require === 'function' ? require('../../../config/profile.js') : {});   // sponsorship "explain" text (JSA-077)
  const explain = (P.work_auth || {}).sponsorship_explain;
  const T = { text: 'text', textarea: 'text', combo: 'combo', select: 'combo', radio: 'radio', checkbox: 'checkbox', multi: 'combo', date: 'date' };   // a date box gets the rule's date (Mets / NJM 2026-11-01)
  const out = {};
  for (const f of list) {
    const label = String(f.label || '').replace(/^\s*(\d+(\.\d+)*|[a-z]\)|q\d+)[.):]?\s+/i, '');   // drop "1.3 " / "Q4." numbering
    const a = answerFor({ l: label, t: T[f.type] || 'text', o: f.type === 'date' ? [] : (f.options || []) }, ctx);   // Workday lists a date's parts (Month/Day/Year) as options (BCBS NE 2026-11-01)
    // guard: a yes/no rule answering a free-text box ("2.4 Family member names" -> "No") is a wrong mapping
    if (a.status === 'ok' && /^(text|textarea)$/.test(f.type) && /^(yes|no)$/i.test(String(a.value)) && !a.yn_text && !/^(sms|age18|relatives|prior_employer|prev_employed|resume_employer|authorized|spons_now|spons_future|gpa_threshold|visa_conditions|qa:\d+)$/.test(a.rule))   // qa:N = the user's own saved answer for this very question (JSA-164); yn_text = the box itself says "If NO, please indicate NO" (Erie SF 11-04)   // "family members employed here?" / "worked here before?" as a text box: No is the answer (Joey 2026-10-30)
    {   // JSA-205: the rule's answer is thrown away — the saved answers (config qa) still get their turn before "unknown"
      const q = typeof answerFor.qaAnswer === 'function' ? answerFor.qaAnswer({ l: label, t: 'text', o: [] }, label) : null;
      out[f.key] = q && q.status === 'ok' ? Object.assign(q, { over: a.rule }) : { status: 'unknown', label, why: 'yes/no rule ' + a.rule + ' on a text box' };
    }
    else if (a.status === 'ok' && /^(text|textarea)$/.test(f.type) && /^spons_(now|future)$/.test(a.rule) && /^yes$/i.test(String(a.value)) && explain && /detail|explain|describe|elaborat/i.test(label))
      out[f.key] = Object.assign({}, a, { value: explain });   // profile: sponsorship "please explain" (Simbe 2026-10-31)
    else out[f.key] = a;   // work authorization / sponsorship as a Lever text box: the Standard answer (Ifm 2026-10-31)
  }
  return out;
}
if (typeof module !== 'undefined' && typeof require !== 'undefined' && require.main === module) {
  const path = require('path');
  const { answerFor } = require(process.argv[2] || path.join(__dirname, '..', 'scripts', 'answer_rules.js'));
  let s = ''; process.stdin.on('data', d => s += d).on('end', () => { const q = JSON.parse(s); const list = Array.isArray(q) ? q : q.fields; process.stdout.write(JSON.stringify(secondOpinion(Array.isArray(q) ? answerAll(answerFor, q) : answerAll(answerFor, q.fields, { jd: q.jd, company: q.company }), list))); });
}
// JSA-202: uncertain rule answers get a second opinion (runner/second_opinion.py, DeepSeek); a disagreement, no answer or
// an error → status unknown, so the runner asks Joey. On only when the runner sets CX_SECOND_OPINION=1; off in tests / replay (JSA_NO_PUSH, CX_DATA).
function secondOpinion(out, list) {
  const env = process.env;
  if (env.CX_SECOND_OPINION !== '1' || env.JSA_NO_PUSH || env.CX_DATA) return out;   // on only in live runner runs (they set CX_SECOND_OPINION=1)
  const byKey = {}; for (const f of list || []) byKey[f.key] = f;
  const items = Object.entries(out).filter(([, a]) => a && a.status === 'ok' && a.uncertain)
    .map(([key, a]) => ({ key, label: a.label, options: (byKey[key] || {}).options || [], type: (byKey[key] || {}).type, value: a.value, rule: a.rule, uncertain: a.uncertain }));
  if (!items.length) return out;
  const path = require('path'), cp = require('child_process');
  const r = cp.spawnSync('python3', [path.join(__dirname, 'second_opinion.py')], { input: JSON.stringify(items), encoding: 'utf8', timeout: 120000 });
  let rev = {}; try { rev = JSON.parse(r.stdout || '{}'); } catch (e) { rev = {}; }
  for (const it of items) {
    const v = rev[it.key];
    if (v && v.agree) out[it.key] = Object.assign({}, out[it.key], { second_opinion: v.why === 'off' ? 'off' : 'agree' });
    else out[it.key] = { status: 'unknown', label: it.label, why: 'second opinion: rules said ' + JSON.stringify(it.value) + ' (' + it.uncertain + '), the model ' + (v && v.model ? 'said ' + JSON.stringify(v.model) : 'gave no answer') + (v && v.why ? ' — ' + v.why : ''), rule: it.rule, rejected: it.value };
  }
  return out;
}
if (typeof module !== 'undefined' && !(typeof require !== 'undefined' && require.main === module)) module.exports = { answerAll };
