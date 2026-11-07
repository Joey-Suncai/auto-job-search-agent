// Lever's confirmation page (/thanks) → the local server records the submit (by: joey) — unless the runner owns this
// folder right now (JSA-083: the extension is in the job Chrome too; the runner records its own submits, by: runner).
chrome.runtime.sendMessage({ kind: 'submitted', url: location.href }, res => {
  const b = (res && res.body) || {};
  const d = document.createElement('div');
  const runner = b.by === 'runner';
  d.textContent = runner ? `Job agent: submitted by the runner — it records this itself (${b.folder})`
    : b.recorded ? `Job agent: recorded as submitted (${b.folder})` : `Job agent: NOT recorded — ${b.error || 'see the server window'}`;
  d.style.cssText = 'position:fixed;top:12px;right:12px;z-index:2147483647;padding:10px 14px;border-radius:8px;font:14px system-ui;color:#fff;background:' + (runner ? '#57606a' : b.recorded ? '#1a7f37' : '#b42318');
  document.body.appendChild(d);
});
