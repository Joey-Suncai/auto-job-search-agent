(()=>{
function __cxVerify(plan) {
  const N = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const digits = s => N(s).replace(/\D/g, '').slice(-10);
  const reactKey = (el, pre) => el && Object.keys(el).find(k => k.startsWith(pre));
  const reactProps = el => { const k = reactKey(el, '__reactProps$'); return k ? el[k] : null; };
  const isVisible = el => { if (!el) return false; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const findEl = f => { try { return document.querySelector(f.sel) || document.getElementsByName(f.key)[0] || null; } catch (e) { return null; } };
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
    const ctrl = el.closest && el.closest('.select__control');
    if (ctrl || f.type === 'combo' || f.type === 'multi') {
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
    if (el.type === 'checkbox') return { dom: el.checked ? 'checked' : '', fw: undefined };
    const p = reactProps(el);
    return { dom: N(el.value), fw: p && 'value' in p ? N(p.value) : undefined };
  }
  function same(f, want, got) {
    if (got == null) return false;
    const acc = [want].concat(f.accept || []).map(N);
    if (f.key === 'phone' || /phone/i.test(f.label || '')) return digits(want) !== '' && digits(want) === digits(got);
    if (f.key === 'location' || /location/i.test(f.key)) return acc.some(a => N(got).toLowerCase().startsWith(a.toLowerCase().split(',')[0]) && N(got).length > 0);
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
  const errRe = /(this field is required|is required\.?$|please (enter|select|fill|provide|complete)|is invalid|invalid (email|phone|format|value)|can't be blank|cannot be blank)/i;
  const legendRe = /indicates a required field|required fields are marked/i;
  const scope = document.querySelector('form') || document.body;
  const seen = new Set();
  scope.querySelectorAll('*').forEach(n => {
    if (n.children.length || (n.textContent || '').length > 160 || !isVisible(n) || legendRe.test(n.textContent || '')) return;
    const styled = /error|invalid/i.test(String(n.className || '') + ' ' + String((n.parentElement && n.parentElement.className) || '')) || n.getAttribute('role') === 'alert';
    if (!errRe.test(n.textContent || '') && !(styled && N(n.textContent))) return;
    if (n.closest('label') && !/error|invalid|helper/i.test(n.className || '')) return;   // a label that merely says "required"
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

const r=__cxVerify({"nonce":"realcheck1","fields":[{"key":"first_name","label":"first_name","type":"text","required":true,"status":"ok","answer":"Test","sel":"#first_name"},{"key":"last_name","label":"last_name","type":"text","required":true,"status":"ok","answer":"Runner","sel":"#last_name"},{"key":"preferred_name","label":"preferred_name","type":"text","required":true,"status":"ok","answer":"Tester","sel":"#preferred_name"},{"key":"email","label":"email","type":"text","required":true,"status":"ok","answer":"test.runner@example.com","sel":"#email"},{"key":"phone","label":"phone","type":"text","required":true,"status":"ok","answer":"2025550143","sel":"#phone"},{"key":"question_69874406","label":"question_69874406","type":"text","required":true,"status":"ok","answer":"Master's","sel":"#question_69874406"},{"key":"question_69874407","label":"question_69874407","type":"textarea","required":true,"status":"ok","answer":"Applied Data Science (M.S.), Economics (B.A.)","sel":"#question_69874407"},{"key":"question_69874410","label":"question_69874410","type":"text","required":true,"status":"ok","answer":"This is a test entry.","sel":"#question_69874410"},{"key":"question_69874412","label":"question_69874412","type":"text","required":true,"status":"ok","answer":"Tester Runner","sel":"#question_69874412"},{"key":"question_69874413","label":"question_69874413","type":"text","required":true,"status":"ok","answer":"Test","sel":"#question_69874413"},{"key":"question_69874414","label":"question_69874414","type":"text","required":true,"status":"ok","answer":"N/A","sel":"#question_69874414"},{"key":"question_69874415","label":"question_69874415","type":"text","required":true,"status":"ok","answer":"Runner","sel":"#question_69874415"},{"key":"question_69874416","label":"question_69874416","type":"text","required":true,"status":"ok","answer":"100 Test Street","sel":"#question_69874416"},{"key":"question_69874417","label":"question_69874417","type":"text","required":true,"status":"ok","answer":"Chicago","sel":"#question_69874417"},{"key":"question_69874419","label":"question_69874419","type":"text","required":true,"status":"ok","answer":"60601","sel":"#question_69874419"},{"key":"question_69874424","label":"question_69874424","type":"text","required":true,"status":"ok","answer":"NONE","sel":"#question_69874424"},{"key":"question_69874426","label":"question_69874426","type":"text","required":true,"status":"ok","answer":"Test University","sel":"#question_69874426"},{"key":"question_69874427","label":"question_69874427","type":"text","required":true,"status":"ok","answer":"linkedin.com/in/test-runner","sel":"#question_69874427"},{"key":"country","label":"country","type":"combo","required":true,"status":"ok","answer":"United States","sel":"#country","accept":["United States","+1"]},{"key":"location","label":"location","type":"combo","required":true,"status":"ok","answer":"Chicago, Illinois, United States","sel":"#candidate-location"},{"key":"question_69874408","label":"question_69874408","type":"combo","required":true,"status":"ok","answer":"Summer (June - August)","sel":"#question_69874408"},{"key":"question_69874409","label":"question_69874409","type":"combo","required":true,"status":"ok","answer":"Other","sel":"#question_69874409"},{"key":"question_69874411","label":"question_69874411","type":"combo","required":true,"status":"ok","answer":"I live INSIDE the United States.","sel":"#question_69874411"},{"key":"question_69874418","label":"question_69874418","type":"combo","required":true,"status":"ok","answer":"Illinois","sel":"#question_69874418"},{"key":"question_69874420","label":"question_69874420","type":"combo","required":true,"status":"ok","answer":"Yes","sel":"#question_69874420"},{"key":"question_69874421","label":"question_69874421","type":"combo","required":true,"status":"ok","answer":"Yes","sel":"#question_69874421"},{"key":"question_69874422","label":"question_69874422","type":"combo","required":true,"status":"ok","answer":"No","sel":"#question_69874422"},{"key":"question_69874423","label":"question_69874423","type":"combo","required":true,"status":"ok","answer":"No","sel":"#question_69874423"},{"key":"question_69874425","label":"question_69874425","type":"combo","required":true,"status":"ok","answer":"No","sel":"#question_69874425"},{"key":"question_69874428","label":"question_69874428","type":"combo","required":true,"status":"ok","answer":"Yes","sel":"#question_69874428"},{"key":"question_69874429","label":"question_69874429","type":"combo","required":true,"status":"ok","answer":"No","sel":"#question_69874429"}]});const dg={};for(const id of ['phone','question_69874407']){const el=document.getElementById(id);const k=el&&Object.keys(el).find(k=>k.startsWith('__reactProps$'));const p=k?el[k]:null;dg[id]={dom:el&&el.value,hasProps:!!p,propKeys:p?Object.keys(p).join(','):'',propValue:p&&'value' in p?p.value:'(none)',defaultValue:p&&p.defaultValue};}return JSON.stringify({pass:r.pass,counts:r.counts,bad:r.bad.map(b=>[b.key,b.layer,b.page,b.framework]),errors:r.errors,diag:dg});})()