// Loads the candidate profile (JSA-077): $JSA_PROFILE → $JSA_HOME/config/profile.json → config/profile.json → config/profile.example.json.
// Node: const P = require('<repo>/config/profile.js').  In a browser page the caller sets globalThis.__cxProfile instead.
const fs = require('fs'), path = require('path');
const os_ = require('os'), tilde = s => s.replace(/^~(?=\/|$)/, os_.homedir());
const pointer = tilde(process.env.JSA_HOME_POINTER || '~/.config/job-search-agent/home');
const home = process.env.JSA_HOME ? path.resolve(tilde(process.env.JSA_HOME))
  : (fs.existsSync(pointer) && fs.readFileSync(pointer, 'utf8').trim() ? path.resolve(tilde(fs.readFileSync(pointer, 'utf8').trim())) : null);   // the data home (ADR-0008); neither = this repo
const pick = [process.env.JSA_PROFILE, home && path.join(home, 'config', 'profile.json'), path.join(__dirname, 'profile.json'), path.join(__dirname, 'profile.example.json')].filter(Boolean);
const file = pick.find(p => fs.existsSync(p));
if (!file) throw new Error('no profile: copy config/profile.example.json to config/profile.json');
module.exports = JSON.parse(fs.readFileSync(file, 'utf8'));
Object.defineProperty(module.exports, '__file', { value: file, enumerable: false });
