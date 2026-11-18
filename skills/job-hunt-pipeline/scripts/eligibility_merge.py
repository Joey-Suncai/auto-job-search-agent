#!/usr/bin/env python3
"""Eligibility gate, step 3: write the verdicts into the dashboard jobs dataset and mark duplicates.

Usage: python3 eligibility_merge.py jobs.json gate_results.json jobs_gated.json [checked_date]
  jobs.json          current datasets/jobs asset (list of rows)
  gate_results.json  from eligibility_classify.js: {row id: {v, c, e, key}}; rows missing here keep their last verdict
                     (elig_base = verdict before duplicate marking, so a row stops being 重复 when its twin disappears)
Adds to every row: elig, elig_reason (Chinese), elig_codes, elig_evidence (English snippet from the JD),
elig_checked, dup_of, tier_orig.
Rules (approved by Joey 2026-10-25):
  Eligible -> 可投; Review / unreadable -> 待核实 (ask him before applying) — but a row whose JD was read before keeps
  that verdict when the JD cannot be read now (elig_read_on = date of that read, elig_read_fail = today; JSA-054); Ineligible -> 不可投 + reason;
  Closed -> 已关闭; same posting listed twice -> 重复 (dup_of = the kept row).
  不可投 / 已关闭 / 重复 rows get tier "Blocked" (original tier kept in tier_orig): hidden by default, never queued.
"""
import json, os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from us_location import is_non_us  # noqa: E402  (JSA-084)
from form_restrictions import apply_form  # noqa: E402  (JSA-231)

REASON = {
    'NO_SPONSORSHIP': ('block', '不提供签证担保'),
    'CITIZEN_OR_CLEARANCE': ('block', '要求美国公民/绿卡、安全许可或出口管制身份'),
    'NON_US': ('block', '不在美国'),
    'OFF_CYCLE': ('block', '不是暑期实习（冬/春/秋季或 co-op）'),
    'TOO_LONG': ('block', '实习期超过 12 周 / 多学期'),
    'UNDERGRAD_ONLY': ('block', '只招本科（大三/大四）'),
    'PHD_ONLY': ('block', '只招博士'),
    # JSA-416: the stated term is before Summer 2027; a postdoc / doctorate already held is required
    'PAST_CYCLE': ('block', '届次已过（JD 写的实习期早于 Summer 2027）'),
    'POSTDOC_OR_PHD_DONE': ('block', '博士后职位，或要求入职前已获博士学位'),
    'EXPERIENCE_3PLUS': ('block', '要求 3 年以上工作经验'),
    'MBA_ONLY': ('block', '只招 MBA'),
    'GRAD_WINDOW': ('block', '毕业时间要求不含 2027 年 12 月'),
    'CLOSED': ('block', '岗位已下线'),
    'FORM_RESTRICTION': ('block', '申请表要求美国公民/绿卡、安全许可或出口管制身份（JD 没写，表单里才出现）'),
    'SPONSORSHIP_MIXED': ('review', '担保说法前后矛盾'),
    'PART_TIME_IN_TERM': ('review', '学期中要兼职'),
    'BACHELORS_WORDING': ('review', 'JD 写的是本科在读'),
    'EXPERIENCE_2': ('review', '要求 2 年经验'),
    'EXPERIENCE_PREFERRED': ('review', '3 年以上经验只写在加分项里（不是硬性要求）'),
    'UNDERGRAD_PREFERRED': ('review', '偏好本科大三/大四（写的是 preferred，不是硬性要求）'),
    'GRAD_MIXED': ('review', '毕业时间要求前后不一'),
    'NO_STEM_OPT': ('review', '不参加 STEM OPT（暑期实习用 CPT 不受影响；全职只有一次 H-1B 抽签机会）'),
    'DS_SECOND_READ': ('review', 'DeepSeek 复读完整 JD 后认为可能能投，与规则不一致，申请前人工核实'),
    'NO_TEXT': ('review', 'JD 太短或读不到'),
    'UNREADABLE': ('review', '读不到 JD（需要登录或网站不支持），申请前人工核实'),
    'FETCH_ERROR': ('review', '读取 JD 出错'),
    'POSSIBLY_EXPIRED': ('review', '网站标注的截止日期已过，可能已关闭，申请前确认'),
    'OFFERS_SPONSORSHIP': ('plus', '明确提供担保'),
    # JSA-385 (Joey 2026-11-17): an internship whose posting only refuses sponsorship is 可投 (CPT needs none)
    'NO_SPONSORSHIP_INTERN': ('plus', '无担保（实习用 CPT）'),
    'NO_FUTURE_SPONSORSHIP_INTERN': ('plus', '无担保，且要求将来也不需担保（实习用 CPT；降一档 C）'),
    'GRAD_OK': ('plus', '毕业时间符合'),
}
VERDICT = {'Eligible': '可投', 'Review': '待核实', 'Ineligible': '不可投', 'Closed': '已关闭', 'Unverified': '待核实'}


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


MANUAL_KEYS = ('elig', 'elig_reason', 'elig_codes', 'elig_evidence', 'dup_of')


def apply_manual(jobs, today):
    """A human verdict on a row must survive the automatic gate (Joey 2026-10-29).

    A row may carry elig_manual = {elig, reason, evidence, codes, dup_of, by, at, until}.
    Until `until` (YYYY-MM-DD, optional) that verdict wins: the automatic verdict of the run is kept in
    elig_auto / elig_auto_at for audit, and every difference is returned as a conflict — reported, never
    silently overwritten. After `until` automation resumes and the row is flagged elig_manual_expired so the
    stale manual call gets re-decided by a human.
    """
    conflicts = []
    for j in jobs:
        m = j.get('elig_manual')
        if not isinstance(m, dict) or not m.get('elig'):
            continue
        until = m.get('until') or ''
        if until and today > until:
            j['elig_manual_expired'] = until
            continue
        auto = j.get('elig')
        j['elig_auto'] = auto
        j['elig_auto_at'] = today
        j['elig'] = m['elig']
        j['elig_reason'] = m.get('reason', j.get('elig_reason', ''))
        if 'codes' in m:
            j['elig_codes'] = m.get('codes') or ''
        if 'evidence' in m:
            j['elig_evidence'] = m.get('evidence') or ''
        j['dup_of'] = m.get('dup_of', '')
        j['tier'] = 'Blocked' if j['elig'] in ('不可投', '已关闭', '重复') else (j.get('tier_orig') or j.get('tier'))
        if auto and auto != j['elig']:
            conflicts.append({'id': j.get('id'), 'manual': j['elig'], 'auto': auto})
    return conflicts


FAILED = ('UNREADABLE', 'FETCH_ERROR')
NOTE = re.compile(r'（\d{4}-\d{2}-\d{2} 读到的 JD；\d{4}-\d{2}-\d{2} 读不到）$')


def apply_result(j, r, checked):
    """One row, one gate result (tested: scripts/test_gate_keep.py). A read failure (UNREADABLE / FETCH_ERROR) keeps the
    verdict of the last successful read, with its date (Joey 2026-10-31, JSA-054: 「保留上一次的结论」)."""
    codes = [c for c in (r.get('c') or '').split(',') if c]
    failed = any(c in FAILED for c in codes)
    pc = j.get('elig_codes') or ''
    pc = pc if isinstance(pc, list) else pc.split(',')            # a few hand-edited rows store a list
    prev_ok = bool(j.get('elig_checked')) and not any(c in FAILED for c in pc)
    # the JD could not be read, but the row's own location is clearly outside the U.S. ("Abu Dhabi", a Workday employer 11-03,
    # JSA-084): that alone is enough to block — no JD needed
    if failed and is_non_us(j.get('location')):
        j.update(elig='不可投', elig_reason=REASON['NON_US'][1], elig_codes='NON_US', elig_evidence=str(j.get('location'))[:120],
                 elig_checked=checked, elig_key=r.get('key', ''), elig_read_fail=checked)
        return
    if failed and prev_ok:
        read_on = j.get('elig_read_on') or j['elig_checked']
        base = NOTE.sub('', j.get('elig_reason') or '')
        j.update(elig_checked=checked, elig_read_on=read_on, elig_read_fail=checked,
                 elig_reason=f'{base}（{read_on} 读到的 JD；{checked} 读不到）')
        return
    lv = 'block' if r['v'] in ('Ineligible', 'Closed') else 'review' if r['v'] in ('Review', 'Unverified') else 'plus'
    why = [REASON[c][1] for c in codes if c in REASON and REASON[c][0] == lv]
    j.update(elig=VERDICT[r['v']], elig_reason='；'.join(why) or ('读到完整 JD，未发现限制' if r['v'] == 'Eligible' else ''),
             elig_codes=','.join(codes), elig_evidence=r.get('e', ''), elig_checked=checked, elig_key=r.get('key', ''))
    if j['elig'] != '已关闭':
        j.pop('elig_closed', None)   # JSA-417: a fresh read found the posting open again — the closed mark no longer holds
    if r.get('ds'):   # JSA-231 phase 2: DeepSeek's second read, kept on the row for the human check
        j['elig_ds'] = r['ds']
    else:
        j.pop('elig_ds', None)
    if failed:
        j['elig_read_fail'] = checked
    else:
        j['elig_read_on'] = checked
        j.pop('elig_read_fail', None)


def main(jobs_p, res_p, out_p, checked='2026-10-26'):
    jobs = json.load(open(jobs_p))
    res = json.load(open(res_p))
    for j in jobs:
        r = res.get(j['id'])
        if not r:  # not re-checked this run: keep the last verdict (before duplicate marking)
            base = j.get('elig_base') or (j.get('elig') if j.get('elig') not in (None, '重复') else '待核实')
            j['elig_base'] = base
            if 'elig' not in j or j['elig'] == '重复':
                j['elig'] = base
            j.setdefault('elig_reason', '还没检查')
            continue
        apply_result(j, r, checked)
        # the old scorer already saw "citizenship required" in the posting text. "Blocked: no sponsorship" no longer blocks
        # (JSA-385): the gate read the JD and decided — a plain refusal is 可投, ranked a little lower by the scorer
        # (a non-internship row keeps the old override: the gate blocks it when it can read the JD, this when it cannot)
        lab = j.get('sponsorship', '')
        intern = j.get('level') == 'Internship' or 'intern' in (j.get('title') or '').lower()
        if lab.startswith('Blocked') and j['elig'] in ('可投', '待核实') and ('no sponsorship' not in lab or not intern):
            j.update(elig='不可投', elig_reason='不提供签证担保' if 'no sponsorship' in lab else '要求美国公民/绿卡')
        if j.get('elig_form'):   # JSA-231: the application form (not the JD) restricts identity — prep found it
            apply_form(j)
        j['elig_base'] = j['elig']
    # ---- dedupe: same posting key, else same company + title + level + location; keep the highest score
    for j in jobs:
        j['dup_of'] = ''
    groups = defaultdict(list)
    for j in jobs:
        k = j.get('elig_key') or ''
        if k and not k.startswith('url:'):
            groups[k].append(j)
        else:
            groups[('sig', norm(j['company']), norm(j['title']), j['level'], norm(j.get('location')))].append(j)
    for g in groups.values():
        g.sort(key=lambda j: (-(j.get('score') or 0), j['id']))
        for d in g[1:]:
            d['dup_of'] = g[0]['id']
    for j in jobs:
        if j['dup_of'] and j['elig_base'] not in ('不可投', '已关闭'):
            j.update(elig='重复', elig_reason=f"与 {j['dup_of']} 是同一个岗位")
        if 'tier_orig' not in j:
            j['tier_orig'] = j.get('tier')
        j['tier'] = 'Blocked' if j['elig'] in ('不可投', '已关闭', '重复') else j['tier_orig']
    conflicts = apply_manual(jobs, checked)
    json.dump(jobs, open(out_p, 'w'), ensure_ascii=False)
    print('verdicts', dict(Counter(j['elig'] for j in jobs)))
    print('internships', dict(Counter(j['elig'] for j in jobs if j['level'] == 'Internship')))
    print('tier', dict(Counter(j['tier'] for j in jobs)))
    if conflicts:
        print('manual_conflicts', len(conflicts), json.dumps(conflicts, ensure_ascii=False))
    return conflicts


if __name__ == '__main__':
    main(*sys.argv[1:])
