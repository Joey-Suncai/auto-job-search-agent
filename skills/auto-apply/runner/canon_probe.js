// In-page probe for canon.py: every SELECTED answer on the form, as {label, value}.
// Independent of plan.json on purpose — it reads what the form would submit.
// The runner calls: page.evaluate(PROBE_SRC + '; __cxCanonProbe()')
function __cxCanonProbe() {
  const N = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const out = [];
  const push = (label, value) => { const v = N(value), l = N(label); if (v && l) out.push({ label: l.slice(0, 140), value: v.slice(0, 140) }); };
  const labelOf = (el, fallback) => {
    if (!el) return fallback || '';
    const aria = el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'));
    if (aria && aria.length < 200) {
      const byId = document.getElementById(aria);
      return byId ? byId.textContent : aria;
    }
    const byFor = el.id && document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
    if (byFor) return byFor.textContent;
    const box = el.closest('div,fieldset,li,[class*="field"]');
    const lab = box && box.querySelector('label,legend');
    return lab ? lab.textContent : (el.name || fallback || '');
  };
  document.querySelectorAll('select').forEach(el => {
    if (el.type === 'hidden' || el.selectedIndex < 0) return;
    const o = el.options[el.selectedIndex];
    if (!o || !o.value) return;
    push(labelOf(el), o.textContent);
  });
  document.querySelectorAll('.select__control').forEach(c => {
    const box = c.parentElement || c;
    const single = box.querySelector('.select__single-value');
    const multi = [...box.querySelectorAll('.select__multi-value__label')].map(n => N(n.textContent));
    const lab = labelOf(c, '');
    if (single) push(lab, single.textContent);
    else if (multi.length) push(lab, multi.join(' | '));
  });
  const seen = new Set();
  document.querySelectorAll('input[type=radio]:checked').forEach(el => {
    const name = el.name || el.id || 'radio';
    if (seen.has(name)) return;
    seen.add(name);
    const own = el.closest('label') || (el.id && document.querySelector('label[for="' + CSS.escape(el.id) + '"]'));
    const group = el.closest('fieldset,[role="group"],[class*="field"]');
    const gl = group && group.querySelector('legend,label');
    push(gl ? gl.textContent : name, own ? own.textContent : el.value);
  });
  document.querySelectorAll('input[type=checkbox]:checked').forEach(el => {
    const own = el.closest('label') || (el.id && document.querySelector('label[for="' + CSS.escape(el.id) + '"]'));
    const group = el.closest('fieldset,[role="group"],[class*="field"]');
    const gl = group && group.querySelector('legend,label');
    push(gl ? gl.textContent : (el.name || ''), own ? own.textContent : el.value);
  });
  return out;
}
if (typeof module !== 'undefined') module.exports = { __cxCanonProbe };
