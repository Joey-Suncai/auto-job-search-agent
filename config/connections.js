// The referrer pool (JSA-195, Joey 2026-11-05): config/connections.json → "connections" = the user's 1st-degree people by
// the company they work at NOW ({"<company key, lower case>": [[name, headline], …]}). "alumni_link" (people who used to
// work somewhere) is not the pool. Order: $JSA_CONNECTIONS → $JSA_HOME/config/connections.json → config/connections.json →
// config/connections.example.json; none = an empty pool. Node: require('<repo>/config/connections.js') →
// {connections: {key: [[name, headline]]}, aliases: {"<other name>": "<pool key>"}} (aliases optional).
// In a browser page the caller sets globalThis.__cxPool (same shape) instead — build_bundle.py embeds it next to the profile.
const fs = require('fs'), path = require('path');
const os_ = require('os'), tilde = s => s.replace(/^~(?=\/|$)/, os_.homedir());
const pointer = tilde(process.env.JSA_HOME_POINTER || '~/.config/job-search-agent/home');
const home = process.env.JSA_HOME ? path.resolve(tilde(process.env.JSA_HOME))
  : (fs.existsSync(pointer) && fs.readFileSync(pointer, 'utf8').trim() ? path.resolve(tilde(fs.readFileSync(pointer, 'utf8').trim())) : null);
const pick = [process.env.JSA_CONNECTIONS, home && path.join(home, 'config', 'connections.json'), path.join(__dirname, 'connections.json'), path.join(__dirname, 'connections.example.json')].filter(Boolean);
const file = pick.find(p => fs.existsSync(p));
const raw = file ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
module.exports = { connections: raw.connections || {}, aliases: raw.aliases || {} };
Object.defineProperty(module.exports, '__file', { value: file || null, enumerable: false });
