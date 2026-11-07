#!/usr/bin/env python3
"""Rebuild cx_bundle.js = profile + referrer pool + form_helpers.js + answer_rules.js (run after editing any of them, the
profile or config/connections.json).
One javascript_tool call installs window.__cx. The profile (config/profile.json, JSA-077) and the referrer pool (config/connections.json → connections, JSA-195) are embedded: cx_bundle.js is
personal data — git-ignored in the public export."""
import json, os, sys
d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(d, '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402
import paths  # noqa: E402  (ADR-0008: the bundle embeds the profile → the data home once JSA_HOME is set)
src = "\n" + jsa_profile.page_js() + open(os.path.join(d, 'form_helpers.js')).read() + "\n" + open(os.path.join(d, 'answer_rules.js')).read() + "\n"
out = paths.bundle(); os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w').write('const __src=' + json.dumps(src) + ';\ntry{localStorage.setItem("__cxb",__src)}catch(e){}\n(0,eval)(__src);\n"cx ready: __cx.extractObj() plan(answers) await run(plan) await fillCombo(id,text) dump()"\n')
print('cx_bundle.js rebuilt' + ('' if out.startswith(d) else ' → ' + out))
