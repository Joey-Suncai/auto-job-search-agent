"""One application folder per job (JSA-319): find a job's folder by its id before making a new one.

The folder name is '<batch date>_<company>_<title>'. Until 2026-11-11 every prep path (prep_batch.py Greenhouse and
Lever / Ashby, prep_wd.py, batch_apply.prep_own) made that name from the batch's date. A job prepared again in a later
batch therefore got a new, empty folder, and the answers Joey had approved in the old one were left behind. an employer
(J16060, SF) lost its approved 193-character ML answer (open_answers.md) and stopped. an Ashby employer (J16166, Ashby) needed
its "Application Date" written by hand again.

Joey's fix (2026-11-11, option 1):
- The newest folder with the same job id is used again when it was never submitted. A folder older than a submitted one is never reused: the job was handed in from a later folder.
- A folder that was submitted is never written into. A true re-submit (JSA-305) gets a new folder, and the approved
  answers are carried into it. Date answers are not carried: they are about the day of the old run.
"""
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ID_FILES = ('job.json', 'wd_job.json')                 # prep_batch / batch_apply / prep_wd write the job id here
CARRY = ('open_answers.md', 'answers.json')             # Joey's approved answers for this job's form
DATE_VALUE = re.compile(r'^\s*(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\s*$')


def slug(s, n=40):
    """Same as prep_batch.slug / batch_apply.folder_name."""
    return re.sub(r'_+', '_', re.sub(r'[^A-Za-z0-9]+', '_', s or '')).strip('_')[:n]


def name_for(date, company, title):
    """Pure (tested). The folder name a new folder gets: '<date>_<company 20>_<title 40>'."""
    return f"{date}_{slug(company, 20)}_{slug(title)}"


def folder_job_id(folder):
    """The job id written in the folder's job.json / wd_job.json, else None."""
    for f in ID_FILES:
        p = os.path.join(folder, f)
        if os.path.exists(p):
            try:
                v = json.load(open(p, encoding='utf-8')).get('id')
            except (OSError, ValueError, AttributeError):
                continue
            if v:
                return str(v)
    return None


def find(job_id, root, company=None, title=None):
    """The folders of this job under `root`, newest first (by the date in the name, then the name). A folder matches by
    the job id in its job.json / wd_job.json. A folder with no id file matches by the same '_<company>_<title>' tail
    (folders from before the id was written)."""
    if not job_id or not os.path.isdir(root):
        return []
    tail = f"_{slug(company, 20)}_{slug(title)}" if company and title else None
    hits = []
    for n in os.listdir(root):
        p = os.path.join(root, n)
        if not os.path.isdir(p) or not re.match(r'\d{4}-\d{2}-\d{2}_', n):
            continue
        fid = folder_job_id(p)
        if fid == str(job_id) or (fid is None and tail and n[10:] == tail):
            hits.append(n)
    return [os.path.join(root, n) for n in sorted(hits, reverse=True)]


def carry(old, new):
    """Copies Joey's approved answers (CARRY) from `old` into `new` when `new` has none yet. answers.json keeps only
    the answers that are not dates. Returns the files carried."""
    done = []
    for f in CARRY:
        src, dst = os.path.join(old, f), os.path.join(new, f)
        if not os.path.exists(src) or os.path.exists(dst):
            continue
        if f == 'answers.json':
            try:
                ans = json.load(open(src, encoding='utf-8'))
            except (OSError, ValueError):
                continue
            keep = {k: v for k, v in ans.items() if not (isinstance(v, str) and DATE_VALUE.match(v))} if isinstance(ans, dict) else ans
            if not keep:
                continue
            json.dump(keep, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        else:
            shutil.copy2(src, dst)
        done.append(f)
    return done


def for_job(job_id, date, company, title, root, submitted, log=print):
    """The folder this job is prepared in (made if new). `submitted(folder)` = True when it was handed in (run_form.
    already_submitted). The newest unsubmitted folder of the job is used again. Otherwise a new folder named for `date`
    is used, with '_r2', '_r3' … added when that name is a submitted folder, and the approved answers of the newest old
    folder are carried in."""
    old = find(job_id, root, company, title)
    for p in old:                                       # newest first; a folder older than a submitted one is superseded
        if submitted(p):                                # (an employer 11-11: the 11-10 dry-run folder, submitted from 11-11's)
            break
        if os.path.basename(p) != name_for(date, company, title):
            log(f"{company}: using the job's existing folder {os.path.basename(p)} (JSA-319)")
        return p
    name, k = name_for(date, company, title), 1
    new = os.path.join(root, name)
    while os.path.isdir(new) and submitted(new):
        k += 1
        new = os.path.join(root, f'{name}_r{k}')
    os.makedirs(new, exist_ok=True)
    if old:
        got = carry(old[0], new)
        if got:
            log(f"{company}: re-submit folder {os.path.basename(new)} — carried {', '.join(got)} from {os.path.basename(old[0])} (JSA-319)")
    return new


def submitted_fn():
    """run_form.already_submitted (results.jsonl), imported late so this module stays light for tests."""
    import run_form as RF
    return RF.already_submitted
