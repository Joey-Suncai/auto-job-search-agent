// "Fill from job agent" on a Lever apply page in Joey's own Chrome (JSA-058). Fills only answers the runner already
// read back in the dry-run (served by lever_fill/server.py), uploads the files, reads every field back and shows a
// panel. It never clicks Submit and never touches a CAPTCHA — Joey does both.
(() => {
  if (document.getElementById('jsa-fill-btn')) return;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const N = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const q = (sel) => document.querySelector(sel);
  const CSS_KEYS = { 'candidate-location': 'select.candidate-location' };   // name-less fields (Lever survey country, JSA-075)
  const byName = (key, extra = '') => CSS_KEYS[key] ? document.querySelector(CSS_KEYS[key]) : document.querySelector(`${extra}[name="${CSS.escape(key)}"]`);
  const fire = (el, ...types) => types.forEach(t => el.dispatchEvent(new Event(t, { bubbles: true })));

  const btn = document.createElement('button');
  btn.id = 'jsa-fill-btn'; btn.type = 'button'; btn.textContent = 'Fill from job agent';
  btn.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:2147483647;padding:12px 18px;border-radius:24px;border:0;font:600 14px system-ui;color:#fff;background:#1f6feb;box-shadow:0 2px 8px rgba(0,0,0,.25);cursor:pointer';
  document.body.appendChild(btn);

  const panel = (lines, good) => {
    let p = document.getElementById('jsa-fill-panel');
    if (!p) { p = document.createElement('div'); p.id = 'jsa-fill-panel'; document.body.appendChild(p); }
    p.style.cssText = 'position:fixed;bottom:76px;right:20px;z-index:2147483647;max-width:420px;max-height:60vh;overflow:auto;padding:12px 14px;border-radius:10px;font:13px/1.45 system-ui;color:#111;background:#fff;border:2px solid ' + (good ? '#1a7f37' : '#b42318') + ';box-shadow:0 2px 10px rgba(0,0,0,.2);white-space:pre-wrap';
    p.textContent = lines.join('\n');
  };

  async function setFile(key, name, b64) {
    const input = byName(key, 'input[type=file]');
    if (!input || !b64) return `file ${key}: ${input ? 'missing on the server' : 'no upload box'}`;
    const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bin], name, { type: name.endsWith('.pdf') ? 'application/pdf' : 'application/octet-stream' }));
    input.files = dt.files; fire(input, 'input', 'change');
    return null;
  }

  async function setField(f) {
    const v = f.value;
    if (f.type === 'radio') {
      const el = [...document.querySelectorAll(`input[type=radio][name="${CSS.escape(f.key)}"]`)].find(x => N(x.value) === N(v));
      if (!el) return 'no option "' + v + '"'; el.click(); return null;
    }
    if (f.type === 'multi') {
      for (const part of v.split(' | ').map(N)) {
        const el = [...document.querySelectorAll(`input[type=checkbox][name="${CSS.escape(f.key)}"]`)].find(x => N(x.value) === part);
        if (!el) return 'no option "' + part + '"'; if (!el.checked) el.click();
      }
      return null;
    }
    if (f.type === 'checkbox') {
      const el = byName(f.key, 'input[type=checkbox]'); if (!el) return 'not on the page';
      const want = /^(yes|true|checked)$/i.test(v); if (el.checked !== want) el.click(); return null;
    }
    if (f.type === 'select') {
      const el = byName(f.key, 'select'); if (!el) return 'not on the page';
      const o = [...el.options].find(x => N(x.text) === N(v) || N(x.value) === N(v)); if (!o) return 'no option "' + v + '"';
      el.value = o.value; fire(el, 'input', 'change'); return null;
    }
    const el = byName(f.key, 'input') || byName(f.key, 'textarea'); if (!el) return 'not on the page';
    if (f.type === 'combo') {                      // location autocomplete: type the city, take the matching suggestion
      const city = v.split(',')[0];
      let opt = null;
      for (let i = 0; i < 40 && !opt; i++) {          // suggestions load from Lever's location API; retype once after 10 s
        if (i === 0 || i === 20) { el.focus(); el.value = ''; fire(el, 'input'); el.value = city; fire(el, 'input', 'keydown', 'keyup', 'change'); }
        await sleep(500);
        opt = [...document.querySelectorAll('.dropdown-location, .location-dropdown li, [role=option]')].find(x => N(x.textContent).toLowerCase().startsWith(city.toLowerCase()));
      }
      if (!opt) { el.value = v; fire(el, 'input', 'change'); return 'no location suggestion — typed the text'; }
      ['mousedown', 'mouseup', 'click'].forEach(t => opt.dispatchEvent(new MouseEvent(t, { bubbles: true })));   // Lever picks on mousedown; a bare click() leaves it empty
      return null;
    }
    el.focus(); el.value = v; fire(el, 'input', 'change'); el.blur();
    return null;
  }

  function readBack(f) {
    if (f.type === 'radio') { const el = document.querySelector(`input[type=radio][name="${CSS.escape(f.key)}"]:checked`); return el ? N(el.value) : ''; }
    if (f.type === 'multi') return [...document.querySelectorAll(`input[type=checkbox][name="${CSS.escape(f.key)}"]:checked`)].map(x => N(x.value)).join(' | ');
    if (f.type === 'checkbox') { const el = byName(f.key, 'input[type=checkbox]'); return el && el.checked ? 'Yes' : 'No'; }
    if (f.type === 'select') { const el = byName(f.key, 'select'); return el && el.selectedIndex >= 0 ? N(el.options[el.selectedIndex].text) : ''; }
    const el = byName(f.key, 'input') || byName(f.key, 'textarea'); return el ? N(el.value) : '';
  }
  const same = (f, got) => {
    const w = N(f.value);
    if (f.type === 'checkbox') return /^(yes|true|checked)$/i.test(w) ? got === 'Yes' : got === 'No';
    if (f.type === 'combo') return got.toLowerCase().startsWith(w.split(',')[0].toLowerCase());
    if (f.type === 'multi') return got.split(' | ').sort().join('|') === w.split(' | ').map(N).sort().join('|');
    if (/phone/i.test(f.key)) return got.replace(/\D/g, '').slice(-10) === w.replace(/\D/g, '').slice(-10);
    return got === w;
  };

  // auto = true on page load (Joey 2026-11-02: the runner opens hCaptcha-stopped pages in his Edge; fill without a click).
  // On load a page the agent has no folder for (404) or cannot serve stays untouched — only a click shows the reason.
  const run = auto => {
    btn.disabled = true; btn.textContent = 'Filling…';
    chrome.runtime.sendMessage({ kind: 'fill', url: location.href }, async res => {
      const b = (res && res.body) || {};
      if (!res || res.status !== 200) {
        if (!auto) panel(['Job agent: nothing filled', b.error || 'no answer from the local server'], false);
        btn.disabled = false; btn.textContent = 'Fill from job agent'; return;
      }
      const problems = [];
      for (const f of b.files) { const e = await setFile(f.key, f.name, f.b64); if (e) problems.push(e); }
      if (b.files.length) { btn.textContent = 'Waiting for Lever resume parsing…'; await sleep(6000); }   // Lever overwrites fields from the resume a few seconds after upload
      for (const f of b.fields) { try { const e = await setField(f); if (e) problems.push(`${f.key}: ${e}`); } catch (e) { problems.push(`${f.key}: ${e}`); } }
      await sleep(800);
      for (const f of b.fields) { const got = readBack(f); if (!same(f, got)) problems.push(`${f.key}: page has "${got.slice(0, 60)}" — want "${N(f.value).slice(0, 60)}"`); }
      const ok = !problems.length;
      panel([ok ? `Job agent: all ${b.fields.length} fields + ${b.files.length} file(s) filled and read back.` : `Job agent: ${problems.length} problem(s) — fix them before Submit:`,
             ...problems, '', `Folder: ${b.folder}`, ok ? 'Check the page, then click Submit yourself. A CAPTCHA, if shown, is yours.' : ''], ok);
      btn.textContent = ok ? 'Filled ✓ — now Submit' : 'Filled with problems'; btn.disabled = false;
    });
  };
  btn.addEventListener('click', () => run(false));
  setTimeout(() => run(true), 1500);                 // let Lever's form finish rendering first
})();
