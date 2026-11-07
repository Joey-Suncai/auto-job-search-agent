#!/usr/bin/env python3
"""Rebuild the cover letter docx + pdf from an edited cover.txt (no DeepSeek call). Usage: python3 rebuild_letter.py <app_folder>
cover.txt layout = greeting, blank line, paragraphs separated by blank lines, then 'Sincerely,' + signature (ignored)."""
import glob, os, re, shutil, sys, tempfile
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds_materials as M
app = os.path.abspath(sys.argv[1])
txt = open(os.path.join(app, 'cover.txt'), encoding='utf8').read().split('\nSincerely,')[0].strip()
blocks = [b.strip() for b in re.split(r'\n\s*\n', txt) if b.strip()]
greeting, paras = blocks[0], blocks[1:]
title, company = re.match(r'# (.+?) — (.+)', open(os.path.join(app, 'jd.md'), encoding='utf8').readline()).groups()
old = glob.glob(os.path.join(app, f'{M.FILE_PREFIX}_Cover_Letter_*.docx'))
name = os.path.basename(old[0]) if old else f'{M.FILE_PREFIX}_Cover_Letter_{M.slug(company)}.docx'
tmp = tempfile.mkdtemp()
lp = os.path.join(tmp, name)
M.build_letter(lp, company, title, greeting, paras, date.today().strftime('%B %-d, %Y'))
pdf = M.to_pdf(lp, tmp)
shutil.copyfile(lp, os.path.join(app, name)); shutil.copyfile(pdf, os.path.join(app, os.path.basename(pdf)))
words = len(re.findall(r"[\w'’-]+", '\n'.join(paras)))
print(f'rebuilt {name} + pdf · {len(paras)} paragraphs · {words} words')
