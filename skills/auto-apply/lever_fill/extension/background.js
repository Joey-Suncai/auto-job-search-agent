// Talks to the local server (skills/auto-apply/lever_fill/server.py, 127.0.0.1 only) for the content scripts.
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  const path = msg.kind === 'submitted' ? '/submitted' : '/lever';
  fetch(`http://127.0.0.1:8765${path}?url=${encodeURIComponent(msg.url)}`, { headers: { 'X-Lever-Fill': '1' } })
    .then(r => r.json().then(j => reply({ status: r.status, body: j })))
    .catch(e => reply({ status: 0, body: { error: 'local server not running: python3 skills/auto-apply/lever_fill/server.py (' + e + ')' } }));
  return true;
});
