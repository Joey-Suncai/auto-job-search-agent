// Compact ATS form helpers for Claude in Chrome (installed via cx_bundle.js = this file + answer_rules.js, one javascript_tool call).
// Installs window.__cx. RETURN TYPES (read this before parsing anything):
//   OBJECT (new, preferred)                          STRING (legacy, JSON text -> JSON.parse it; kept for old briefs)
//   __cx.extractObj()  -> [{i,k,l,t,r,o?,v,m?}]      __cx.extract()  -> JSON string of the same list
//   __cx.autoObj()     -> {fill,click,unknown,..}    __cx.auto()     -> JSON string (answer_rules.js)
//   __cx.fillObj(map)  -> {unset:[...]}              __cx.fill(map)  -> JSON string {"unset":[...]}
//   __cx.dump()        -> object (see dump below)    __cx.dumpText() -> old "i|label|value" lines as one string
//   __cx.plan(answers?)-> object {actions,unknown,consent,files,notes}            (sync)
//   await __cx.run(plan?) -> dump object + {results,newFields}                    (async: returns a Promise)
//   await __cx.fillCombo(idOrLabelOrIndex, optionText | [alternatives], {multi?}) -> {ok,value} | {ok:false,error,candidates}  (async)
// Fields: i = index (also data-cx on the element), k = id/name, l = label, t = text|email|textarea|select|radio|checkbox|combo|toggle|file|...,
//         r = required 1/0, o = options (select/radio/checkbox), v = current value, m = 1 if multi-select combo.
// Never submits, never touches password fields.
(() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const norm = s => clean(s).toLowerCase().replace(/&/g, 'and').replace(/\s*\/\s*/g, '/').replace(/[.,;:!?]+$/, '');
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return (r.width > 0 || r.height > 0 || e.type === 'file') && s.visibility !== 'hidden' && s.display !== 'none'; };
  const labelFor = id => id ? [...document.querySelectorAll('label')].find(l => l.htmlFor === id) : null;
  const SKIPPH = /^select\.*$/i;
  const labelOf = e => {
    let t = '';
    if (e.getAttribute('aria-labelledby')) t = e.getAttribute('aria-labelledby').split(' ').map(id => document.getElementById(id)?.innerText || document.getElementById(id)?.textContent || '').join(' ');
    if (!clean(t) && e.id) { const l = labelFor(e.id); if (l) t = l.innerText || l.textContent; }
    if (!clean(t)) t = e.closest('label')?.innerText || '';
    if (!clean(t)) t = e.getAttribute('aria-label') || '';
    if (!clean(t)) { const f = e.closest('fieldset'); if (f) t = f.querySelector('legend')?.innerText || ''; }
    if (!clean(t)) { // nearest preceding text in the same field container
      let c = e.parentElement;
      for (let n = 0; n < 4 && c && !clean(t); n++, c = c.parentElement) {
        const l = c.querySelector('label, legend, [class*="label" i], [class*="question" i]');
        if (l && !l.contains(e)) t = l.innerText || l.textContent;
      }
    }
    if (!clean(t) || SKIPPH.test(clean(t))) { // Greenhouse react-select: aria-labelledby points at the "Select..." placeholder
      t = ''; let c = e.parentElement;
      for (let n = 0; n < 7 && c && !clean(t); n++, c = c.parentElement) {
        const l = [...c.querySelectorAll('label, legend')].find(x => !x.contains(e) && clean(x.innerText || x.textContent) && !SKIPPH.test(clean(x.innerText || x.textContent)));
        if (l) t = l.innerText || l.textContent;
      }
    }
    let out = clean(t || e.placeholder || e.name);
    if (/^(month|year|mm|yyyy)$/i.test(out)) { // education dates: bare "Month"/"Year" -> "Start date Month"
      const lg = e.closest('fieldset, [role="group"]')?.querySelector('legend, [class*="legend" i], [class*="label" i]');
      const hint = clean(lg?.innerText || lg?.textContent) || (/start/i.test(e.id + e.name) ? 'Start date' : /end/i.test(e.id + e.name) ? 'End date' : '');
      if (hint && !/^(month|year)$/i.test(hint)) out = hint + ' ' + out;
    }
    return out.slice(0, 140);
  };
  const groupLabel = e => { // label of a radio/checkbox group (question text), not of the single option
    const f = e.closest('fieldset, [role="radiogroup"], [role="group"]');
    if (f) { const l = f.querySelector('legend') || (f.getAttribute('aria-labelledby') && document.getElementById(f.getAttribute('aria-labelledby').split(' ')[0]));
      if (l && clean(l.innerText || l.textContent)) return clean(l.innerText || l.textContent).slice(0, 140); }
    let c = e.parentElement;
    for (let n = 0; n < 6 && c; n++, c = c.parentElement) {
      const l = [...c.querySelectorAll('label, legend, [class*="label" i]')].find(x => !x.querySelector('input') && !x.contains(e));
      if (l && clean(l.innerText || l.textContent)) return clean(l.innerText || l.textContent).slice(0, 140);
    }
    return labelOf(e);
  };
  const reqOf = (e, l) => (e.required || e.getAttribute('aria-required') === 'true' || /\*\s*$|\(required\)/i.test(l)) ? 1 : 0;

  // ---- react-select helpers
  const comboRoot = e => { const c = e.closest('[class*="__control"], [class*="-control"]'); return (c && c.parentElement) || e.closest('[class*="select-shell"], [class*="select__container"]') || e.parentElement?.parentElement || e.parentElement; };
  const comboValues = e => { const root = comboRoot(e);
    return root ? [...root.querySelectorAll('[class*="single-value"], [class*="singleValue"], [class*="multi-value__label"], [class*="MultiValue"] [class*="label" i]')].map(x => clean(x.innerText || x.textContent)).filter(Boolean) : []; };
  const isCombo = e => e.matches('[role="combobox"]') || e.getAttribute('aria-autocomplete') || (e.tagName === 'INPUT' && e.closest('[class*="select__control"], [class*="select__container"], [class*="select-shell"], [class*="Select-control"]'));

  // ---- scan: every visible field, with element refs (el / els) kept in window.__cxFields
  const scan = () => {
    const out = []; const groups = {}; let i = 0, skipped = 0; const raw = document.querySelectorAll('input, textarea, select, [role="combobox"], button[aria-pressed]');
    const visit = e => {
      if (e.closest('#simplify-jobs-container, [id^="simplify"]')) return;
      const t = e.tagName === 'SELECT' ? 'select' : e.tagName === 'TEXTAREA' ? 'textarea'
        : e.matches('[role="combobox"]') || e.getAttribute('aria-autocomplete') ? 'combo'
        : e.tagName === 'BUTTON' ? 'toggle'
        : (e.tagName === 'INPUT' && isCombo(e)) ? 'combo' : (e.type || 'text');
      if (['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes(t) || !vis(e)) return;
      if (t === 'radio' || t === 'checkbox') {
        const key = (e.name || groupLabel(e));
        const opt = clean(e.closest('label')?.innerText || (e.id && labelFor(e.id)?.innerText) || e.value).slice(0, 60);
        if (groups[key]) { const g = groups[key]; g.o.push(opt); g.els.push(e); if (e.checked) g.v.push(opt); return; }
        const gl = groupLabel(e);
        const g = { i, k: key.slice(0, 60), l: gl, t, r: reqOf(e, gl), o: [opt], v: e.checked ? [opt] : [], els: [e] };
        groups[key] = g; e.dataset.cx = i; out.push(g); i++; return;
      }
      if (e.tagName === 'INPUT' && e.parentElement?.closest('[role="combobox"]') && t !== 'file') return; // inner input of a combo: skip
      if (e.tagName === 'INPUT' && !e.matches('[role="combobox"]') && t !== 'file' && e.closest('[class*="select-shell"], [class*="select__container"]')?.querySelector('[role="combobox"]')) return; // react-select hidden required-input
      const l = labelOf(e);
      if (t === 'combo' && out.length && out[out.length - 1].t === 'combo' && out[out.length - 1].l === l && out[out.length - 1].el === e) return;
      e.dataset.cx = i;
      const f = { i, k: (e.id || e.name || '').slice(0, 60), l, t, r: reqOf(e, l), v: t === 'file' ? (e.files?.[0]?.name || '') : clean(e.value).slice(0, 200), el: e };
      if (t === 'select') f.o = [...e.options].map(o => clean(o.text)).filter(Boolean).slice(0, 25);
      if (t === 'toggle') f.v = e.getAttribute('aria-pressed');
      if (t === 'combo') { const vals = comboValues(e); f.v = vals.join('; ').slice(0, 200);
        if (vals.length > 1 || comboRoot(e)?.querySelector('[class*="multi-value"]') || /multi/i.test(comboRoot(e)?.className || '')) f.m = 1; }
      out.push(f); i++;
    };
    raw.forEach(e => { try { visit(e); } catch (err) { skipped++; } });
    window.__cxFields = out; window.__cxScan = { raw: raw.length, skipped };
    return out;
  };
  const strip = ({ el, els, ...f }) => ({ ...f, v: Array.isArray(f.v) ? f.v.join('; ') : f.v });
  const extractObj = () => scan().map(strip);
  const extract = () => JSON.stringify(extractObj());

  // ---- setters
  const setNative = (e, val) => {
    const proto = e.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : e.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, val);
    e.dispatchEvent(new Event('input', { bubbles: true }));
    e.dispatchEvent(new Event('change', { bubbles: true }));
    e.dispatchEvent(new Event('blur', { bubbles: true }));
  };
  const setSelect = (e, val) => {
    const w = norm(val);
    const o = [...e.options].find(o => norm(o.text) === w) || [...e.options].find(o => norm(o.text).startsWith(w));
    if (!o) return false; e.value = o.value; e.dispatchEvent(new Event('change', { bubbles: true })); return true;
  };
  const clickOpt = (o) => ['mouseover', 'mousemove', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']
    .forEach(t => o.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window, button: 0 })));
  const setCheck = (f, want) => { // want: array of option texts (radio/checkbox group) -> true if every wanted option ends up checked
    const w = want.map(norm); const yes = x => ['yes', 'true', 'checked', 'on'].includes(x);
    const ons = f.els.map((e, n) => w.includes(norm(f.o[n])) || (f.els.length === 1 && w.some(yes)));
    f.els.forEach((e, n) => { if (ons[n] !== e.checked && (ons[n] || f.t === 'checkbox')) e.click(); });
    return ons.some(Boolean) && ons.every((on, n) => !on || f.els[n].checked);
  };

  // ---- legacy fill (text/textarea/select/radio/checkbox). Combos -> use fillCombo.
  const fillObj = map => {
    const fields = window.__cxFields || scan(); const miss = [];
    for (const [k, val] of Object.entries(map)) {
      const f = fields.find(x => String(x.i) === String(k)) || fields.find(x => x.k === k);
      if (!f) { miss.push(k + ': no such field'); continue; }
      if (f.t === 'radio' || f.t === 'checkbox') { if (!setCheck(f, Array.isArray(val) ? val : [val])) miss.push(k + ': no option matched ' + [].concat(val).join('/')); continue; }
      if (!f.el?.isConnected) { miss.push(k + ': element gone'); continue; }
      if (f.t === 'select') { if (!setSelect(f.el, String(val))) miss.push(k + ': option not found'); }
      else if (f.t === 'combo') miss.push(k + ': combo -> await __cx.fillCombo(' + f.i + ', "...")');
      else if (['file', 'toggle'].includes(f.t)) miss.push(k + `: ${f.t} needs click/file_upload`);
      else setNative(f.el, String(val));
    }
    return { unset: miss };
  };
  const fill = map => JSON.stringify(fillObj(map));

  // ---- fillCombo: ONE async call for a react-select (focus, filter, wait for options, pick, read back)
  const findCombo = key => {
    if (key && key.nodeType === 1) return { el: key.matches('[role="combobox"], input') ? key : key.querySelector('[role="combobox"], input:not([type=hidden])') };
    if (typeof key === 'number' || /^\d+$/.test(String(key))) { const f = (window.__cxFields || scan()).find(x => x.i === Number(key)); return f && f.el ? { el: f.el } : { error: 'no field index ' + key }; }
    const byId = document.getElementById(String(key));
    if (byId) { const el = byId.matches('input, [role="combobox"]') ? byId : byId.querySelector('[role="combobox"], input:not([type=hidden])'); if (el) return { el }; }
    const fields = scan().filter(f => f.t === 'combo'); const w = norm(key);
    for (const test of [f => norm(f.l) === w, f => norm(f.l).startsWith(w), f => norm(f.l).includes(w), f => f.k === String(key)]) {
      const hit = fields.filter(test); if (hit.length === 1) return { el: hit[0].el }; if (hit.length > 1) return { error: 'ambiguous label', candidates: hit.map(f => f.i + ':' + f.l.slice(0, 60)) };
    }
    return { error: 'combo not found: ' + key };
  };
  const optionsOf = (input, root) => {
    const lb = input.getAttribute('aria-controls') && document.getElementById(input.getAttribute('aria-controls'));
    let o = lb ? [...lb.querySelectorAll('[role="option"]')] : [];
    if (!o.length && root) o = [...root.querySelectorAll('[role="option"]')];
    if (!o.length && root) o = [...root.querySelectorAll('[id*="-option-"], [class*="__option"]')];
    return o;
  };
  const noticeOf = (input, root) => { const n = (root && root.querySelector('[class*="menu-notice"], [class*="NoOptionsMessage"], [class*="LoadingMessage"], [class*="no-options"], [class*="loading-message"]')) || null; return n ? clean(n.innerText || n.textContent) : ''; };
  const waitOptions = async (input, root, ms = 3000) => { // poll until options (or a "No options" notice) are stable for two consecutive polls
    const t0 = Date.now(); let last = null, same = 0;
    while (Date.now() - t0 < ms) {
      await sleep(60);
      const opts = optionsOf(input, root); const note = noticeOf(input, root); const loading = /loading/i.test(note);
      const sig = opts.map(o => clean(o.innerText || o.textContent)).join('|') + '#' + (opts.length ? '' : note);
      if (!loading && (opts.length || note) && sig === last) { if (++same >= 2) return { opts, timeout: false }; } else same = 0;
      last = sig;
    }
    return { opts: optionsOf(input, root), timeout: true };
  };
  const setInput = (input, v) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, v); input.dispatchEvent(new Event('input', { bubbles: true })); };
  const choose = (texts, target) => { // exact, then unique word-start, then unique contains; ambiguous -> {amb}
    const w = norm(target); const n = texts.map(norm);
    const idx = (fn) => n.map((x, k) => fn(x) ? k : -1).filter(k => k >= 0);
    const ex = idx(x => x === w); if (ex.length) return { k: ex[0] };
    const st = idx(x => x.startsWith(w) && (x.length === w.length || !/[a-z0-9]/.test(x[w.length] || ''))); if (st.length === 1) return { k: st[0] }; if (st.length > 1) return { amb: st };
    const st2 = idx(x => x.startsWith(w)); if (st2.length === 1) return { k: st2[0] }; if (st2.length > 1) return { amb: st2 };
    const ct = idx(x => x.includes(w)); if (ct.length === 1) return { k: ct[0] }; if (ct.length > 1) return { amb: ct };
    return {};
  };
  const pickOne = async (input, text, multi) => {
    const root = comboRoot(input);
    const have = comboValues(input).map(norm);
    if (have.includes(norm(text)) || (!multi && have.length && choose(have, text).k === 0)) return { ok: true, value: comboValues(input).join('; '), already: true };
    input.focus();
    let res = null;
    for (const phase of ['filter', 'all']) {
      if (phase === 'filter') setInput(input, text);
      else { setInput(input, ''); input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', keyCode: 40, bubbles: true, cancelable: true })); }
      const { opts, timeout } = await waitOptions(input, root);
      const texts = opts.map(o => clean(o.innerText || o.textContent));
      const c = choose(texts, text);
      if (c.amb) return { ok: false, error: 'ambiguous', candidates: c.amb.map(k => texts[k]).slice(0, 20) };
      if (c.k !== undefined) { res = { opt: opts[c.k], text: texts[c.k] }; break; }
      res = { fail: { ok: false, error: texts.length ? 'no matching option' : (timeout ? 'options never loaded (3s)' : 'no options'), candidates: texts.slice(0, 20) } };
    }
    if (!res.opt) { setInput(input, ''); input.blur(); return res.fail; }
    if (input.getAttribute('aria-controls') && document.getElementById(input.getAttribute('aria-controls'))?.getAttribute('aria-multiselectable') === 'true') multi = true;
    for (let attempt = 0; attempt < 2; attempt++) {
      clickOpt(res.opt);
      for (let n = 0; n < 15; n++) { await sleep(100); const vals = comboValues(input).map(norm); if (multi ? vals.includes(norm(res.text)) : (vals.length && vals[0] === norm(res.text))) {
          setInput(input, ''); input.blur(); return { ok: true, value: comboValues(input).join('; '), picked: res.text }; } }
      const again = optionsOf(input, root).find(o => clean(o.innerText || o.textContent) === res.text); if (again) res.opt = again; else break;
    }
    const cur = comboValues(input).join('; '); setInput(input, ''); input.blur();
    return { ok: false, error: 'click did not register', value: cur, picked: res.text };
  };
  const fillCombo = async (key, optionText, opts = {}) => {
    const f = findCombo(key); if (!f.el) return { ok: false, ...f };
    const input = f.el; const multi = !!opts.multi || /multi/i.test(comboRoot(input)?.className || '') || !!comboRoot(input)?.querySelector('[class*="multi-value"]');
    if (multi && Array.isArray(optionText)) { // multi-select: pick every listed option
      const done = []; for (const t of optionText) { const r = await pickOne(input, t, true); if (!r.ok) return { ...r, value: comboValues(input), failedOn: t, done }; done.push(r.picked || t); }
      return { ok: true, value: comboValues(input) };
    }
    const alts = [].concat(optionText); let last = null;
    for (const t of alts) { const r = await pickOne(input, String(t), multi); if (r.ok) return multi ? { ...r, value: comboValues(input) } : r; last = r; if (r.error === 'ambiguous') return { ...r, tried: t }; }
    return { ...last, tried: alts };
  };

  // ---- dump: object covering ALL fields
  const dump = () => {
    const fields = scan(); const rows = []; const empty = [];
    for (const f of fields) {
      let v = Array.isArray(f.v) ? f.v.join('; ') : f.v;
      if (f.t === 'textarea') v = v ? `[${v.length < 200 ? v.length : (f.el.value || '').length} chars] ${v.slice(0, 30)}` : '';
      else if (f.t === 'checkbox' && f.o.length === 1) v = f.v.length ? 'checked' : 'unchecked';
      else if (f.t === 'file') v = v ? 'file: ' + v : '';
      else if (f.t === 'toggle') v = v === 'true' ? 'on' : v === 'false' ? 'off' : (v || '');
      else v = (v || '').slice(0, 60);
      rows.push(`${f.i}|${f.r ? '*' : ''}${f.l.slice(0, 60)}|${v}`);
      if (f.r && (!v || v === 'unchecked') && f.t !== 'toggle') empty.push(f.i);
    }
    const errors = [...new Set([...document.querySelectorAll('[role="alert"], [class*="error" i], [class*="invalid" i]')]
      .filter(x => !x.querySelector('input, textarea, select') && (x.getBoundingClientRect().width > 0 || x.getBoundingClientRect().height > 0))
      .map(x => clean(x.innerText || x.textContent)).filter(x => x && x.length < 200))].slice(0, 20);
    const invalid = fields.filter(f => (f.el || f.els?.[0])?.getAttribute('aria-invalid') === 'true').map(f => f.i);
    return { n: fields.length, raw: window.__cxScan.raw, skipped: window.__cxScan.skipped, rows, empty_required: empty, errors, invalid };
  };
  const dumpText = () => dump().rows.join('\n');

  // ---- plan / run
  const selOf = f => { const e = f.el || f.els[0]; return e.id ? `[id="${e.id}"]` : e.name ? `input[name="${e.name}"]` : `[data-cx="${f.i}"]`; };
  const plan = (answers = {}) => {
    const AR = globalThis.__answerRules || window.__answerRules; if (!AR) throw new Error('answer_rules not loaded (use cx_bundle.js)');
    const fields = scan(); window.__cxPlanFields = fields;
    const actions = [], unknown = [], consent = [], files = [], notes = [];
    const over = f => { const ks = Object.keys(answers); const k = ks.find(k => String(k) === String(f.i)) ?? ks.find(k => norm(k) === norm(f.l)) ?? ks.find(k => norm(k) && norm(f.l).includes(norm(k)));
      return k === undefined ? undefined : answers[k]; };
    const act = (f, action, value, why) => actions.push({ i: f.i, l: f.l.slice(0, 60), t: f.t, action, ...(value !== undefined ? { value } : {}), ...(why ? { why } : {}) });
    for (const f of fields) {
      const cur = Array.isArray(f.v) ? f.v.join('; ') : (f.v || '');
      if (f.t === 'file') { files.push({ i: f.i, label: f.l.slice(0, 60), selector: selOf(f), required: f.r, current: cur }); act(f, 'file', undefined, selOf(f)); continue; }
      if (f.t === 'password') { act(f, 'skip', undefined, 'password: never'); continue; }
      if (/--[1-9]\d*$/.test(f.k)) { act(f, 'skip', undefined, 'extra education/experience block'); continue; }
      let a; const o = over(f);
      if (o !== undefined) a = { status: 'ok', value: (o && o.value !== undefined) ? o.value : o, multi: o && o.multi };
      else a = AR.answerFor({ i: f.i, l: f.l, t: f.t, o: f.o, r: f.r }, { jd: window.__cxJd, company: window.__cxCompany });   // set window.__cxCompany = the hiring company first (referrer pool, JSA-195)
      if (a.status === 'consent') { consent.push({ i: f.i, label: f.l.slice(0, 100) }); act(f, 'skip', undefined, 'consent: ask Joey'); continue; }
      if (a.status === 'unknown') { unknown.push({ i: f.i, label: f.l, type: f.t, required: !!f.r, ...(f.o ? { options: f.o.slice(0, 12) } : {}), ...(a.why ? { why: a.why } : {}) }); act(f, 'skip', undefined, 'unknown'); continue; }
      if (a.note) notes.push(f.l.slice(0, 50) + ': ' + a.note);
      if (a.leave) { act(f, 'skip', undefined, 'leave unchecked'); continue; }
      const val = a.alts || a.value; const first = [].concat(val)[0];
      if (f.t === 'combo') {
        if (cur && [].concat(val).some(x => choose([cur], String(x)).k === 0)) { act(f, 'skip', undefined, 'already: ' + cur.slice(0, 30)); continue; }
        actions.push({ i: f.i, l: f.l.slice(0, 60), t: f.t, action: 'combo', value: val, ...(a.multi || f.m ? { multi: 1 } : {}) });
      } else if (['radio', 'checkbox', 'toggle'].includes(f.t)) {
        const have = (Array.isArray(f.v) ? f.v : [f.v]).map(norm);
        if (have.includes(norm(first))) { act(f, 'skip', undefined, 'already set'); continue; }
        act(f, 'check', first);
      } else {
        if (norm(cur) === norm(first)) { act(f, 'skip', undefined, 'already set'); continue; }
        act(f, 'text', String(first));
      }
    }
    const p = { actions, unknown: unknown.sort((x, y) => y.required - x.required), consent, files, notes, counts: { fields: fields.length, act: actions.filter(a => a.action !== 'skip' && a.action !== 'file').length, unknown: unknown.length } };
    window.__cxPlan = p; return p;
  };
  const run = async (p = window.__cxPlan) => {
    if (!p) throw new Error('no plan: call __cx.plan() first');
    const fields = window.__cxPlanFields || scan(); const results = []; const known = new Set(fields.map(f => f.el || f.els?.[0]));
    for (const a of p.actions || []) {
      if (!['text', 'combo', 'check'].includes(a.action)) continue;
      const f = fields.find(x => x.i === a.i); const r = { i: a.i, l: (a.l || '').slice(0, 40), action: a.action };
      try {
        if (!f || !(f.el || f.els?.[0])?.isConnected) { r.ok = false; r.error = 'element gone (page re-rendered: call plan() again)'; }
        else if (a.action === 'combo') Object.assign(r, await fillCombo(f.el, a.value, { multi: !!a.multi }));
        else if (a.action === 'check') {
          if (f.t === 'toggle') { const want = ['yes', 'true', 'on'].includes(norm(a.value)); if ((f.el.getAttribute('aria-pressed') === 'true') !== want) f.el.click(); r.ok = true; }
          else { r.ok = setCheck(f, [].concat(a.value)); if (!r.ok) r.error = 'option not matched: ' + a.value; } }
        else if (f.t === 'select') { r.ok = setSelect(f.el, a.value); if (!r.ok) r.error = 'option not found: ' + a.value; }
        else { setNative(f.el, String(a.value)); r.ok = f.el.value === String(a.value); }
      } catch (err) { r.ok = false; r.error = String(err && err.message || err); }
      if (r.ok && r.value === undefined) delete r.value;
      results.push(r); await sleep(a.action === 'combo' ? 80 : 20);
    }
    await sleep(150);
    const d = dump(); const after = window.__cxFields;
    const newFields = after.filter(f => !known.has(f.el || f.els?.[0])).map(f => ({ i: f.i, l: f.l.slice(0, 60), t: f.t, r: f.r, ...(f.o ? { o: f.o.slice(0, 10) } : {}) }));
    const bad = results.filter(r => !r.ok);
    return { ...d, results: results.map(r => r.ok ? `${r.i}:ok` : r), failed: bad.length, newFields, note: newFields.length ? 'new fields appeared: call plan() again then run()' : undefined };
  };

  window.__cx = { extract, extractObj, fill, fillObj, dump, dumpText, fillCombo, plan, run, norm };
  return 'cx ready';
})();
