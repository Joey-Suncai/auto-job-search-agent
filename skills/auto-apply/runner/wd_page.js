// Workday in-page helpers, evaluated by run_wd.py (never relayed by an agent).
// __wdExtract()  → {step, url, auth, fields:[{key, label, required, type, options, value, section, sel, aid}]}
//   key = data-cx-k stamped on the field container (stable while the page lives); type: text | textarea | select | prompt |
//   radio | checkbox | multi | date | file.  section = the repeat block heading ("Work Experience 1", "Education 2") if any.
// __wdErrors()   → visible Workday error messages.
function __wdN(s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); }
function __wdVis(e) { return !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden'; }
function __wdStep() {
  const a = document.querySelector('[data-automation-id="progressBarActiveStep"]');
  return __wdN(a ? a.textContent : '').replace(/^current step \d+ of \d+\s*/i, '');
}
function __wdAuth() {
  const pw = [...document.querySelectorAll('input[type="password"]')].some(__wdVis);
  const st = __wdStep();
  // social sign-in chooser (Apple / Google / LinkedIn / email) has no password field yet (Hitachi 2026-10-30)
  const social = [...document.querySelectorAll('[data-automation-id="SignInWithEmailButton"]')].some(__wdVis);
  return pw || social || /^(create account|sign in)/i.test(st);
}
function __wdExtract() {
  const N = __wdN;
  window.__cxN = window.__cxN || 0;
  const labOf = x => { const l = x.id && document.querySelector('label[for="' + CSS.escape(x.id) + '"]'); return N(l ? l.textContent : ((x.closest('label') || {}).textContent || x.getAttribute('aria-label') || x.value)); };
  const out = [];
  document.querySelectorAll('[data-automation-id^="formField-"], [data-automation-id="formField"]').forEach(box => {
    if (!__wdVis(box)) return;
    if (box.parentElement && box.parentElement.closest('[data-automation-id^="formField-"]')) return;   // nested
    let k = box.getAttribute('data-cx-k');
    if (!k) { k = 'w' + (++window.__cxN); box.setAttribute('data-cx-k', k); }
    const labEl = box.querySelector('label, legend, [data-automation-id="formLabel"]');
    let label = N(labEl ? labEl.textContent : '');
    const required = /\*/.test(label) || !!box.querySelector('[aria-required="true"], [required]');
    label = label.replace(/\*/g, '').replace(/\(required\)/i, '').trim();
    // a named sub-group (e.g. "Preferred Name" → First Name / Last Name) gives the label its context
    const sub = box.closest('[role="group"][aria-labelledby]:not([aria-labelledby$="-panel"]):not([aria-labelledby$="-section"])');
    const subH = sub && document.getElementById((sub.getAttribute('aria-labelledby') || '').split(' ')[0]);
    const subT = subH ? N(subH.textContent) : '';
    const aidK = box.getAttribute('data-automation-id') || '';
    if ((/preferred name/i.test(subT) || /preferredName/i.test(aidK)) && !/preferred/i.test(label)) label = 'Preferred ' + label;
    // repeat block context (Work Experience 1 / Education 2 / Websites 1 …)
    let section = '';
    let panel = '';
    const grp = box.closest('[role="group"][aria-labelledby$="-panel"]');     // repeat block (date sub-groups are role=group too)
    if (grp) {
      panel = grp.getAttribute('aria-labelledby');
      const he = document.getElementById(panel.split(' ')[0]);
      section = N(he ? he.textContent : panel.replace(/-panel$/, '').replace(/-/g, ' '));
    }
    let type = 'text', options = [], value = '';
    const btn = box.querySelector('button[aria-haspopup="listbox"]');
    const prompt = box.querySelector('[data-automation-id="multiselectInputContainer"], [data-uxi-widget-type="selectinput"], [data-automation-id="selectinput"]');
    const radios = [...box.querySelectorAll('input[type="radio"]')];
    const cbs = [...box.querySelectorAll('input[type="checkbox"]')];
    const dates = [...box.querySelectorAll('input[data-automation-id^="dateSection"]')];
    const file = box.querySelector('input[type="file"]');
    const ta = box.querySelector('textarea');
    const inp = box.querySelector('input[type="text"], input[type="email"], input[type="tel"], input[type="number"], input:not([type])');
    if (btn) { type = 'select'; value = N(btn.textContent); if (/^select one$|^select$/i.test(value)) value = ''; }
    else if (prompt) { type = 'prompt'; value = [...box.querySelectorAll('[data-automation-id="selectedItem"], [data-automation-id="selectedItemList"] li')].map(x => N(x.textContent)).filter(Boolean).join(' | '); }
    else if (radios.length) { type = 'radio'; options = radios.map(labOf); const on = radios.find(r => r.checked); value = on ? labOf(on) : ''; }
    else if (dates.length) { type = 'date'; value = dates.map(x => x.value).filter(Boolean).join('/'); options = dates.map(x => x.getAttribute('data-automation-id').replace(/^dateSection|-input$/g, '')); }
    else if (cbs.length > 1) { type = 'multi'; options = cbs.map(labOf); value = cbs.filter(c => c.checked).map(labOf).join(' | '); }
    else if (cbs.length === 1) { type = 'checkbox'; value = cbs[0].checked ? 'checked' : ''; if (!label) label = labOf(cbs[0]); options = [labOf(cbs[0])]; }
    else if (file) { type = 'file'; }
    else if (ta) { type = 'textarea'; value = ta.value; }
    else if (inp) { type = 'text'; value = inp.value; }
    else return;
    out.push({ key: k, label, required, type, options, value: N(value), section, panel, sel: '[data-cx-k="' + k + '"]', aid: box.getAttribute('data-automation-id') });
  });
  return { step: __wdStep(), url: location.href, auth: __wdAuth(), fields: out };
}
function __wdErrors() {
  const out = [];
  document.querySelectorAll('[data-automation-id="errorMessage"], [data-automation-id="inputAlert"], [role="alert"]').forEach(e => {
    const t = __wdN(e.textContent);
    if (!t || !__wdVis(e) || out.includes(t) || /success|uploaded|saved|^loading/i.test(t)) return;   // status toasts are not errors
    out.push(t.slice(0, 160));
  });
  return out;
}
if (typeof module !== 'undefined') module.exports = { __wdExtract, __wdErrors };
