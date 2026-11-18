#!/usr/bin/env python3
"""Cases for skill_gap.gap_list / todo_row (JSA-194); expected values derived by hand from the rules in the module docstring.
    python3 scripts/test_skill_gap.py   → "fails 0" """
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import skill_gap as S

def rec(folder, company, day, gaps):
    return {'folder': folder, 'company': company, 'generated_at': day + 'T10:00:00', 'gaps_not_true': gaps}
T = '2026-11-17'
R = [rec('f1', 'A', '2026-11-16', ['RAG', 'cross-functional']), rec('f2', 'B', '2026-11-15', ['rag', 'backend']),
     rec('f3', 'C', '2026-11-10', ['RAG', 'RAG']), rec('f4', 'D', '2026-11-12', ['cross-functional']),
     rec('f5', 'E', '2026-10-01', ['RAG', 'backend']),               # too old
     rec('f6', 'A', '2026-11-16', ['backend']), rec('f7', 'A', '2026-11-16', ['backend'])]
fails = 0
def check(name, cond, detail=''):
    global fails
    if not cond: fails += 1; print('FAIL', name, detail)
    else: print('ok  ', name)

g = S.gap_list(R, T)
rag = next((x for x in g if x['term'].lower() == 'rag'), {})
check('RAG: 3 recent folders (f1, f2, f3; f3 counts once; f5 too old), 3 companies', rag.get('folders') == 3 and rag.get('companies') == 3, g)
check('ties on folders sort by term: backend before RAG', [x['term'] for x in g] == ['backend', 'RAG'], g)
check('cross-functional only 2 folders → below the threshold', all(x['term'] != 'cross-functional' for x in g), g)
check('backend: 3 folders but 2 companies (A twice) → listed with companies 2', any(x['term'] == 'backend' and x['folders'] == 3 and x['companies'] == 2 for x in S.gap_list(R, T, min_companies=2)), g)
check('backend dropped when 3 companies are needed', all(x['term'] != 'backend' for x in S.gap_list(R, T, min_companies=3)))
check('window: a 60-day window brings f5 in (RAG 4)', next(x for x in S.gap_list(R, T, days=60) if x['term'].lower() == 'rag')['folders'] == 4)
check('spelling: the most frequent one is shown (RAG ×2 vs rag ×1)', rag.get('term') == 'RAG')
check('share = 3 / 6 recent folders', rag.get('share') == 0.5, rag)
check('empty / bad input', S.gap_list([], T) == [] and S.gap_list([{'folder': 'x'}], T) == [] and S.gap_list(None, T) == [])
row = S.todo_row([rag], T)
check('todo row is a skill-gap row that asks, not claims', row and row['kind'] == 'skill-gap' and 'RAG (3)' in row['msg'] and 'nothing is added' in row['next'], row)
check('no row when the list is empty', S.todo_row([], T) is None)
print('fails', fails); sys.exit(1 if fails else 0)
