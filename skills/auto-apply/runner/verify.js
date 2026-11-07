// In-page verifier. The runner (Playwright) calls:  page.evaluate(VERIFY_SRC + '; __cxVerify(plan)')
// It is run by OUR code and its JSON is written to <app>/verify.json by the runner — never relayed by an agent.
// Layers:
//   L1 page value     what the page shows (input value, react-select single-value, <select> option, checked radio/checkbox)
//   L2 framework      what React holds (controlled input props.value / react-select state value) — catches "shows text, React doesn't know"
//   L3 form errors    visible required/invalid messages, aria-invalid, required inputs still empty, hidden required values (lat/long)
// Result: { nonce, pass, counts, bad:[...], errors:[...] }. pass = every planned field passes L1 and L2 and there are no L3 errors.
function __cxVerify(plan) {
  const N = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const digits = s => N(s).replace(/\D/g, '').slice(-10);
  const reactKey = (el, pre) => el && Object.keys(el).find(k => k.startsWith(pre));
  const reactProps = el => { const k = reactKey(el, '__reactProps$'); return k ? el[k] : null; };
  const isVisible = el => { if (!el) return false; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const findEl = f => { try { return document.querySelector(f.sel) || document.getElementsByName(f.key)[0] || null; } catch (e) { return null; } };

  // react-select: walk the fiber tree up from the input to the Select component (props has options + onChange + value)
  function reactSelectState(el) {
    const k = reactKey(el, '__reactFiber$'); if (!k) return undefined;
    let fb = el[k];
    for (let i = 0; fb && i < 40; i++, fb = fb.return) {
      const p = fb.memoizedProps;
      if (p && typeof p === 'object' && 'onChange' in p && ('options' in p || 'loadOptions' in p) && 'value' in p && !('getValue' in p) && !('selectOption' in p)) {   // skip react-select's inner Input/Option parts (their value = typed text)
        const v = p.value;
        if (v == null) return '';
        if (Array.isArray(v)) return v.map(x => N(x && (x.label ?? x.value))).join(' | ');
        return N(typeof v === 'object' ? (v.label ?? v.value) : v);
      }
    }
    return undefined;   // not found → L2 "n/a" for this field
  }

  function read(f, el) {
    if (!el) return { dom: null, fw: undefined, missing: true };
    // a checkbox group whose selector resolved to its <fieldset>/role=group wrapper (Greenhouse multi-select questions)
    const group = (el.tagName === 'FIELDSET' || el.getAttribute('role') === 'group') && el.querySelector('input[type=checkbox]') ? el : null;
    if (group) {
      const on = [...group.querySelectorAll('input[type=checkbox]')].filter(x => x.checked).map(x => {
        const l = (x.id && document.querySelector('label[for="' + CSS.escape(x.id) + '"]')) || x.closest('label');
        return N(l ? l.textContent : x.value); });
      return { dom: on.join(' | '), fw: undefined };
    }
    const ctrl = el.closest && el.closest('.select__control');
    if (ctrl || ((f.type === 'combo' || f.type === 'multi') && el.type !== 'checkbox' && el.type !== 'radio' && el.tagName !== 'SELECT')) {
      const box = ctrl ? ctrl.parentElement : el.parentElement;
      const single = box && box.querySelector('.select__single-value');
      const multi = box ? [...box.querySelectorAll('.select__multi-value__label')].map(n => N(n.textContent)) : [];
      const dom = single ? N(single.textContent) : multi.join(' | ');
      return { dom, fw: reactSelectState(el) };
    }
    if (el.tagName === 'SELECT') { const o = el.options[el.selectedIndex]; return { dom: o && o.value !== '' ? N(o.text) : '', fw: undefined }; }
    if (el.type === 'radio' || f.type === 'radio') {
      const group = [...document.getElementsByName(el.name || f.key)].filter(x => x.type === 'radio');
      const on = group.find(x => x.checked);
      return { dom: on ? N(on.value) : '', fw: undefined };
    }
    if (el.type === 'checkbox' && (f.type === 'multi' || /\[\]$/.test(f.key) || (f.options || []).length > 1)) {   // checkbox group (multi-select)
      const box = el.closest('fieldset, [role="group"], .checkbox-group, [class*="field"]') || document;
      const on = [...box.querySelectorAll('input[type=checkbox]')].filter(x => x.checked).map(x => {
        const l = (x.id && document.querySelector('label[for="' + CSS.escape(x.id) + '"]')) || x.closest('label');
        return N(l ? l.textContent : x.value); });
      return { dom: on.join(' | '), fw: undefined };
    }
    if (el.type === 'checkbox') return { dom: el.checked ? 'checked' : '', fw: undefined };
    const p = reactProps(el);
    // uncontrolled inputs pass value={undefined}: React holds nothing, the DOM value is what gets submitted → L2 n/a
    return { dom: N(el.value), fw: p && p.value !== undefined && p.value !== null ? N(p.value) : undefined };
  }

  // a phone-NUMBER box only: a Yes/No question whose text mentions "telephone calls" is not one (Xaira SMS consent 2026-10-31)
  function isPhone(f) { return f.key === 'phone' || (/^(text|tel)$/.test(f.type || 'text') && /\bphone\b/i.test(f.label || '') && !(f.options || []).length); }
  function same(f, want, got) {
    if (got == null) return false;
    const acc = [want].concat(f.accept || []).map(N);
    if (isPhone(f)) return digits(want) !== '' && digits(want) === digits(got);
    if (f.key === 'location' || /location/i.test(f.key)) return acc.some(a => N(got).toLowerCase().startsWith(a.toLowerCase().split(',')[0]) && N(got).length > 0);
    if (f.type === 'multi' && N(got) && acc.includes(N(got))) return true;
    if (f.type === 'multi' && N(got)) { const set = x => N(x).split(' | ').map(N).sort().join(' | ');
      if (acc.some(a => set(a) === set(got))) return true; }
    if (f.type === 'checkbox') return (want === true || /^(yes|true|checked)$/i.test(N(want))) ? got === 'checked' : got === '';
    if (/^(text|textarea)$/.test(f.type) && /linkedin|url|website/i.test(f.label || f.key))
      return acc.some(a => a.replace(/^https?:\/\/(www\.)?/i, '').replace(/\/$/, '') === N(got).replace(/^https?:\/\/(www\.)?/i, '').replace(/\/$/, ''));
    if (f.type === 'combo' || f.type === 'multi') return acc.includes(N(got)) || acc.some(x => x && N(got).startsWith(x + ' '));
    return acc.includes(N(got));
  }

  const res = { nonce: plan.nonce, url: location.href, checked_at: new Date().toISOString(), pass: false,
    counts: { fields: 0, l1_ok: 0, l2_ok: 0, l2_na: 0 }, bad: [], errors: [] };

  for (const f of plan.fields || []) {
    if (f.status === 'check_only') {               // hidden required value set by a widget (e.g. latitude)
      const el = findEl(f);
      if (el && f.required && !N(el.value)) res.errors.push({ key: f.key, msg: 'hidden required value empty' });
      continue;
    }
    if (f.status !== 'ok') continue;
    res.counts.fields++;
    const el = findEl(f);
    const r = read(f, el);
    const l1 = same(f, f.answer, r.dom);
    const l2 = r.fw === undefined ? null : same(f, f.answer, r.fw);
    if (l1) res.counts.l1_ok++;
    if (l2 === null) res.counts.l2_na++; else if (l2) res.counts.l2_ok++;
    if (!l1 || l2 === false) res.bad.push({ key: f.key, label: N(f.label).slice(0, 60), want: N(f.answer).slice(0, 80),
      page: r.missing ? 'MISSING' : N(r.dom).slice(0, 80), framework: r.fw === undefined ? 'n/a' : N(r.fw).slice(0, 80),
      layer: !l1 ? 'L1' : 'L2' });
  }

  // L3: visible error messages and invalid markers
  const errRe = /(this field is required|is required\.?$|please (enter|select|fill|provide|complete)|is invalid|invalid (email|phone|format|value)|can't be blank|cannot be blank)/i;
  const legendRe = /indicates a required field|required fields are marked/i;
  const scope = document.querySelector('form') || document.body;
  const seen = new Set();
  scope.querySelectorAll('*').forEach(n => {
    if (n.children.length || (n.textContent || '').length > 160 || !isVisible(n) || legendRe.test(n.textContent || '')) return;
    const styled = /error|invalid/i.test(String(n.className || '') + ' ' + String((n.parentElement && n.parentElement.className) || '')) || n.getAttribute('role') === 'alert';
    if (!errRe.test(n.textContent || '') && !(styled && N(n.textContent))) return;
    if (n.closest('label') && !/error|invalid|helper/i.test(n.className || '')) return;   // a label that merely says "required"
    if (!styled && n.closest('[id$="-description"], .question-description, [class*="description"]')) return;   // question help text ("please select all that apply")
    const field = n.closest('[class*="field"], .application-question, fieldset, li');
    const lab = field && field.querySelector('label');
    const key = N(lab ? lab.textContent : n.textContent).slice(0, 70);
    if (!seen.has(key)) { seen.add(key); res.errors.push({ key, msg: N(n.textContent).slice(0, 80) }); }
  });
  document.querySelectorAll('[aria-invalid="true"]').forEach(el => {
    if (!isVisible(el)) return;
    const key = 'aria-invalid:' + (el.id || el.name || '');
    if (!seen.has(key)) { seen.add(key); res.errors.push({ key, msg: 'aria-invalid' }); }
  });
  res.pass = res.counts.fields > 0 && res.bad.length === 0 && res.errors.length === 0;
  return res;
}
if (typeof module !== 'undefined') module.exports = { __cxVerify };
