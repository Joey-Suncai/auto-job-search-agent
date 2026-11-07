#!/usr/bin/env python3
"""Unpack the A-Classic TEMPLATE into scripts/un/ and merge its runs, so build_a.py can rebuild the four bases from
scratch (JSA-012). Self-contained — replaces the docx skill's merge_runs.py, which is not on this Mac.

    python3 prepare_template.py            # → scripts/un/ (overwrites)
    python3 prepare_template.py --check    # only report the run counts of the paragraph templates build_a.py uses

Merge rule: inside one paragraph, adjacent <w:r> runs with the same run properties (rsid attributes ignored) become one
run; <w:proofErr>, <w:lastRenderedPageBreak> and empty bookmark pairs between them are dropped. Text is never changed.
"""
import os, re, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import jsa_profile  # noqa: E402  (JSA-077)
TEMPLATE = os.path.join(ROOT, jsa_profile.get('resume_template') or 'resume/TEMPLATE.docx')
# paragraph index → number of <w:t> build_a.fill() fills (resume-updater SKILL §"Paragraph templates")
EXPECT = {0: 1, 1: 1, 2: 1, 3: 2, 7: 3, 8: 2, 13: 2, 16: 1, 17: 2, 18: 1, 25: 3}

RSID = re.compile(r' w:rsid\w*="[^"]*"')
RUN = re.compile(r'<w:r(?: [^>]*)?>(?:(?!</w:r>).)*?</w:r>', re.S)
NOISE = re.compile(r'<w:proofErr [^>]*/>|<w:lastRenderedPageBreak/>|<w:bookmarkStart [^>]*/><w:bookmarkEnd [^>]*/>')


def _parts(run):
    rpr = re.search(r'<w:rPr>.*?</w:rPr>', run, re.S)
    body = run[run.index('>') + 1:-len('</w:r>')]
    if rpr:
        body = body.replace(rpr.group(0), '', 1)
    m = re.fullmatch(r'\s*<w:t(?: [^>]*)?>([^<]*)</w:t>\s*', body)
    return (RSID.sub('', rpr.group(0)) if rpr else ''), (m.group(1) if m else None)


def merge_paragraph(p):
    p = NOISE.sub('', p)
    out, last = [], None          # last = (rpr, text, index in out)
    pos = 0
    for m in RUN.finditer(p):
        between = p[pos:m.start()]
        rpr, text = _parts(m.group(0))
        if last and not between.strip() and text is not None and last[0] == rpr and last[1] is not None:
            merged = last[1] + text
            out[last[2]] = f'<w:r>{rpr}<w:t xml:space="preserve">{merged}</w:t></w:r>'
            last = (rpr, merged, last[2])
        else:
            out.append(between)
            out.append(m.group(0) if text is None else f'<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r>')
            last = (rpr, text, len(out) - 1)
        pos = m.end()
    out.append(p[pos:])
    return ''.join(out)


def merge_runs(xml):
    return re.sub(r'<w:p[ >].*?</w:p>', lambda m: merge_paragraph(m.group(0)), xml, flags=re.S)


def counts(xml):
    P = re.findall(r'<w:p[ >].*?</w:p>', xml, flags=re.S)
    return {i: len(re.findall(r'<w:t(?: [^>]*)?>', P[i])) for i in EXPECT}


def main(a):
    dst = os.path.join(HERE, 'un')
    if '--check' in a:
        print(counts(open(os.path.join(dst, 'word', 'document.xml'), encoding='utf-8').read())); return 0
    shutil.rmtree(dst, ignore_errors=True)
    with zipfile.ZipFile(TEMPLATE) as z:
        z.extractall(dst)
    for d, _, files in os.walk(dst):           # no symlinks in an unpacked docx (resume-updater SKILL step 1)
        for f in files:
            if os.path.islink(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
    dp = os.path.join(dst, 'word', 'document.xml')
    xml = merge_runs(open(dp, encoding='utf-8').read())
    open(dp, 'w', encoding='utf-8').write(xml)
    got = counts(xml)
    bad = {i: (got[i], n) for i, n in EXPECT.items() if got[i] != n}
    print('un/ ready' if not bad else f'run counts differ (index: got, want): {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
