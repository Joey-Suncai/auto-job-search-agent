#!/usr/bin/env python3
"""Harness for the 2026-11-03 Workday fixes (rule 13: DeepSeek wrote the cases from the specs, Claude judges):
JSA-065 zero_field_experience · JSA-067 source_pick / real_options · JSA-068 file_kind / files_for_field ·
JSA-071 is_review_page / step_changed · joey_step (assessment steps, type O). Verdicts (case misreads the spec) in test_cases/<name>_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd

def run(name, call):
    cases = json.load(open(os.path.join(HERE, 'test_cases', f'{name}_cases.json')))
    vp = os.path.join(HERE, 'test_cases', f'{name}_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        if c.get('ambiguous') and c['name'] in verdicts: continue
        got = call(c)
        if got != c['expect'] and c['name'] not in verdicts:
            bad += 1; print(f'DISAGREE {name}/{c["name"]} | got {got!r} | expect {c["expect"]!r} | {json.dumps(c, ensure_ascii=False)[:300]}')
    print(f'{name}: {len(cases)} cases · disagreements without a verdict: {bad}')
    return bad

def src(c):
    return run_wd.source_pick(c['options']) if c['fn'] == 'source_pick' else run_wd.real_options(c['options'])

def files(c):
    a = c['args']
    if c['fn'] == 'file_kind': return run_wd.file_kind(a['label'])
    return run_wd.files_for_field(a['kind'], a['field_text'], a['resume'], a.get('cover'), a['want_cover'], a['multiple'])

def review(c):
    a = c['args']
    if c['fn'] == 'is_review_page': return run_wd.is_review_page(a['step'], a['fields'])
    return run_wd.step_changed(a['before_step'], a['before_keys'], a['after_step'], a['after_keys'])

bad = (run('wd_source_pick', src) + run('wd_zero_fields', lambda c: run_wd.zero_field_experience(c['sections'], c['upload_ok'], c['body_text']))
       + run('wd_files', files) + run('wd_review_step', review) + run('wd_joey_step', lambda c: run_wd.joey_step(c['step']))
       + run('wd_human_check', lambda c: bool(run_wd.HUMAN_CHECK_RX.search(c['label']))))
sys.exit(1 if bad else 0)
