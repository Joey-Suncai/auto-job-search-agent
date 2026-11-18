#!/usr/bin/env python3
"""DeepSeek cases (scripts/test_cases/llm_vendor_terms_cases.json, rule 13, JSA-278): the lexicon keeps Claude / Anthropic apart
from ChatGPT / OpenAI / GPT; plus the built role files must not carry the old mixed group. Verdicts in
scripts/test_cases/llm_vendor_terms_verdicts.json. Run: python3 skills/resume-updater/scripts/test_llm_vendor_terms.py"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import role_library as R  # noqa: E402
lex = json.load(open(os.path.join(R.ROLES, 'lexicon.json'), encoding='utf-8'))
comp = R.compile_lexicon(lex)
groups = [g for g in comp['agents']['groups'] if g[0] in ('Claude', 'ChatGPT')]
def vendor_hits(text):
    return sorted(g[0] for g in groups if any(m.search(text) for m in g[2]))
cases = json.load(open(os.path.join(REPO, 'scripts', 'test_cases', 'llm_vendor_terms_cases.json')))
vp = os.path.join(REPO, 'scripts', 'test_cases', 'llm_vendor_terms_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
if [g[0] for g in groups] != ['Claude', 'ChatGPT']:
    bad += 1; print('lexicon: expected groups Claude and ChatGPT, got', [g[0] for g in groups])
for c in cases:
    got = vendor_hits(c['text'])
    if got != sorted(c['expect']) and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
import paths  # noqa: E402  (config/ is on sys.path via role_library)
for dname in ('ai_pm', 'ai_agentic', 'data_analyst', 'data_engineer'):
    f = paths.data('roles', dname + '.json')   # the rebuilt library only: the repo's roles/*.json are old seeds (fallback copies)
    if not os.path.exists(f):
        continue
    d = json.load(open(f, encoding='utf-8'))
    for c in d.get('competencies', []):
        for k in c.get('keywords', []):
            if k.get('term') == 'Claude' and set(k.get('synonyms') or []) - {'Anthropic'}:
                bad += 1; print('role file still mixes other vendors into Claude:', f)
# ds_materials must read the role library through paths.role_file, not the code dir's stale seed
src = open(os.path.join(REPO, 'skills', 'auto-apply', 'scripts', 'ds_materials.py'), encoding='utf-8').read()
if 'os.path.join(TL.ROLES' in src:
    bad += 1; print('ds_materials reads role json from TL.ROLES (stale seed)')
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
