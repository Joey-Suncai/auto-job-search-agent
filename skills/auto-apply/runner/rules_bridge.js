// Answers a list of plan fields with the standard rules (skills/auto-apply/scripts/answer_rules.js — the single source).
// Node:    echo '[{key,label,type,options}]' | node rules_bridge.js <answer_rules.js>   → {key: answerFor result}
//          or echo '{"fields": [...], "jd": "<JD text>", "company": "<hiring company>"}' — rules with jd: true answer from the JD
//          (JSA-105); referral questions check the company against the referrer pool (JSA-195) — no company = they are asked
// Browser: plan_build.py evaluates this file + answer_rules.js and calls answerAll(answerFor, list) (Macs without Node).
// JSA-322: a text box whose question a bare Yes / No answers. Pure (tested: scripts/test_yn_textbox.py).
const YN_START = /^\W*(are|is|am|do|does|did|will|would|can|could|have|has|had|were|was|should|may|must)\b/i;
const YN_MARK = /\(\s*(yes\s*\/\s*no|y\s*\/\s*n)\s*\)|\byes or no\b|\banswer (yes|no)\b/i;
const OPEN_TEXT = /\b(any(thing)? (other|else|additional|further)|anything else|additional (context|information|details|comments)|context|elaborate|explain|describe|details?\b|comments?|share|tell us|let us know (more|about)|list|names?)\b/i;   // no wh-words: 'require sponsorship … where the role is based?' is still yes/no
function ynTextBox(label) {
  const q = String(label || '').replace(/\s+/g, ' ').trim();
  if (YN_MARK.test(q)) return true;
  if (!YN_START.test(q)) return false;
  const first = q.split(/\?/)[0];                    // the asking sentence only: "Do you need sponsorship? If so, please list …" is a yes/no box
  return !OPEN_TEXT.test(first);
}
function answerAll(answerFor, list, ctx) {
  const P = globalThis.__cxProfile || (typeof require === 'function' ? require('../../../config/profile.js') : {});   // sponsorship "explain" text (JSA-077)
  const explain = (P.work_auth || {}).sponsorship_explain;
  const T = { text: 'text', textarea: 'text', combo: 'combo', select: 'combo', radio: 'radio', checkbox: 'checkbox', multi: 'combo', date: 'date' };   // a date box gets the rule's date (Mets / NJM 2026-11-01)
  const out = {};
  for (const f of list) {
    const label = String(f.label || '').replace(/^\s*(\d+(\.\d+)*|[a-z]\)|q\d+)[.):]?\s+/i, '');   // drop "1.3 " / "Q4." numbering
    const a = answerFor({ l: label, t: T[f.type] || 'text', o: f.type === 'date' ? [] : (f.options || []) }, ctx);   // Workday lists a date's parts (Month/Day/Year) as options (BCBS NE 2026-11-01)
    // guard: a yes/no rule answering a free-text box ("2.4 Family member names" -> "No") is a wrong mapping. JSA-322 (Joey
    // 2026-11-11, option A): the box's own question decides, not the rule. A bare Yes / No goes into a text box only when
    // the box asks a yes/no question ("Will you require sponsorship?") and does not invite more text (a Greenhouse employer 11-10: "Is there
    // any other context you'd like to share about your sponsorship needs?" got "Yes" from spons_future). The work-
    // authorization / sponsorship rules were let into every text box; now only into a yes/no one. The other listed rules
    // keep their text-box answer (Joey 2026-10-30: "family members employed here?" as a text box = No), as do the user's
    // own saved answer (qa:N) and "If NO, please indicate NO" (yn_text).
    const exp = a.status === 'ok' && /^(text|textarea)$/.test(f.type) && /^spons_(now|future)$/.test(a.rule) && /^yes$/i.test(String(a.value)) && explain && /detail|explain|describe|elaborat/i.test(label);
    if (exp) out[f.key] = Object.assign({}, a, { value: explain });   // profile: sponsorship "please explain" (Simbe 2026-10-31) — before the guard (an employer 10-31)
    else if (a.status === 'ok' && /^(text|textarea)$/.test(f.type) && /^(yes|no)$/i.test(String(a.value)) && !a.yn_text
        && !/^(sms|age18|relatives|prior_employer|prev_employed|resume_employer|gpa_threshold|visa_conditions|qa:\d+)$/.test(a.rule)
        && !(/^(authorized|spons_now|spons_future|any_employer|auth_today)$/.test(a.rule) && ynTextBox(label))
        && !(a.rule === 'citizenship_country' && /^yes$/i.test(String(a.value)) && ynTextBox(label)))   // JSA-381: a country-list yes / no question in a text box keeps its Yes   // qa:N = the user's own saved answer for this very question (JSA-164); yn_text = the box itself says "If NO, please indicate NO" (Erie SF 11-04)   // "family members employed here?" / "worked here before?" as a text box: No is the answer (Joey 2026-10-30)
    {   // JSA-205: the rule's answer is thrown away — the saved answers (config qa) still get their turn before "unknown"
      const q = typeof answerFor.qaAnswer === 'function' ? answerFor.qaAnswer({ l: label, t: 'text', o: [] }, label) : null;
      out[f.key] = q && q.status === 'ok' ? Object.assign(q, { over: a.rule }) : { status: 'unknown', label, why: 'yes/no rule ' + a.rule + ' on a text box' };
    }
    else out[f.key] = a;   // work authorization / sponsorship as a Lever text box: the Standard answer (Ifm 2026-10-31)
  }
  return out;
}
if (typeof module !== 'undefined' && typeof require !== 'undefined' && require.main === module) {
  const path = require('path');
  const { answerFor } = require(process.argv[2] || path.join(__dirname, '..', 'scripts', 'answer_rules.js'));
  let s = ''; process.stdin.on('data', d => s += d).on('end', () => { const q = JSON.parse(s); const list = Array.isArray(q) ? q : q.fields; process.stdout.write(JSON.stringify(secondOpinion(Array.isArray(q) ? answerAll(answerFor, q) : answerAll(answerFor, q.fields, { jd: q.jd, company: q.company, cover: q.cover }), list))); });
}
// JSA-202: uncertain rule answers get a second opinion (runner/second_opinion.py, DeepSeek); a disagreement, no answer or
// an error → status unknown, so the runner asks Joey. On only when the runner sets CX_SECOND_OPINION=1; off in tests / replay (JSA_NO_PUSH, CX_DATA).
function secondOpinion(out, list) {
  const env = process.env;
  if (env.CX_SECOND_OPINION !== '1' || env.JSA_NO_PUSH || env.CX_DATA) return out;   // on only in live runner runs (they set CX_SECOND_OPINION=1)
  const byKey = {}; for (const f of list || []) byKey[f.key] = f;
  const items = Object.entries(out).filter(([, a]) => a && a.status === 'ok' && a.uncertain)
    .map(([key, a]) => ({ key, label: a.label, options: (byKey[key] || {}).options || [], type: (byKey[key] || {}).type, value: a.value, rule: a.rule, uncertain: a.uncertain }));
  const path = require('path'), cp = require('child_process');
  if (items.length) {
  const r = cp.spawnSync('python3', [path.join(__dirname, 'second_opinion.py')], { input: JSON.stringify(items), encoding: 'utf8', timeout: 120000 });
  let rev = {}; try { rev = JSON.parse(r.stdout || '{}'); } catch (e) { rev = {}; }
  for (const it of items) {
    const v = rev[it.key];
    if (v && v.agree) out[it.key] = Object.assign({}, out[it.key], { second_opinion: v.why === 'off' ? 'off' : 'agree' });
    else out[it.key] = { status: 'unknown', label: it.label, why: 'second opinion: rules said ' + JSON.stringify(it.value) + ' (' + it.uncertain + '), the model ' + (v && v.model ? 'said ' + JSON.stringify(v.model) : 'gave no answer') + (v && v.why ? ' — ' + v.why : ''), rule: it.rule, rejected: it.value };
  }
  }
  return wholeRead(out, list, path, cp);
}
// JSA-288 (Joey 2026-11-10): every rule-answered critical question (scripts/field_class.py; work authorization, education,
// record, experience) is read whole by DeepSeek on its own (runner/whole_read.py, cached per question); a different
// answer, UNSURE or an error → status unknown, the runner asks Joey. whole_read.py picks the questions; CX_WHOLE_READ=0 = off.
function wholeRead(out, list, path, cp) {
  if (process.env.CX_WHOLE_READ === '0') return out;
  const labels = (list || []).map(f => f.label || ''), pos = {}; (list || []).forEach((f, i) => { pos[f.key] = i; });
  const byKey = {}; for (const f of list || []) byKey[f.key] = f;
  const items = Object.entries(out).filter(([, a]) => a && a.status === 'ok' && !a.leave && a.rule)
    .map(([key, a]) => ({ key, label: (byKey[key] || {}).label || a.label, options: (byKey[key] || {}).options || [], type: (byKey[key] || {}).type, value: a.value, rule: a.rule, pos: pos[key],
      context: pos[key] === undefined ? [] : labels.slice(Math.max(0, pos[key] - 4), pos[key]) }));
  if (!items.length) return out;
  const r = cp.spawnSync('python3', [path.join(__dirname, 'whole_read.py')], { input: JSON.stringify(items), encoding: 'utf8', timeout: 180000 });
  let rev = null; try { rev = JSON.parse(r.stdout || 'null'); } catch (e) { rev = null; }
  if (!rev) {   // the reader itself failed: every critical answer is unconfirmed → ask (never submit unread)
    rev = {}; const sel = cp.spawnSync('python3', [path.join(__dirname, 'whole_read.py'), '--select'], { input: JSON.stringify(items), encoding: 'utf8', timeout: 60000 });
    let keys = []; try { keys = JSON.parse(sel.stdout || '[]'); } catch (e) { keys = items.map(i => i.key); }
    for (const k of keys) rev[k] = { agree: false, model: null, why: 'whole read failed: ' + String(r.stderr || r.error || '').slice(-120) };
  }
  for (const it of items) {
    const v = rev[it.key];
    if (!v) continue;                                            // not a critical question the reader covers
    if (v.agree) out[it.key] = Object.assign({}, out[it.key], { whole_read: 'agree' });
    else out[it.key] = { status: 'unknown', label: out[it.key].label || it.label, why: 'whole read: rules said ' + JSON.stringify(it.value) + ' (' + it.rule + '), the model ' + (v.model ? 'said ' + JSON.stringify(v.model) : 'gave no answer') + (v.why ? ' — ' + v.why : ''), rule: it.rule, rejected: it.value, whole_read: v.how || 'disagree' };
  }
  return out;
}
if (typeof module !== 'undefined' && !(typeof require !== 'undefined' && require.main === module)) module.exports = { answerAll, ynTextBox };
