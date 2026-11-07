"""Readability + wording check for the candidate's resumes (resume-updater §7).
Usage: python3 check_resume.py file.docx [more.docx ...]   (expects file.pdf next to each .docx)
Checks (sources in resume-updater SKILL.md):
  - 1 page; last text line reaches the page (fill)                      -> fill.py does the precise measure
  - margins >= 0.5 in (720 twips) on all sides                           (MIT CAPD)
  - every bullet <= 2 lines; no bullet whose last line is a single word  (Ladders: long sentences hurt)
  - banned buzzwords                                                      (TopResume 2025: AI-sounding text)
  - bullets without a number (X-Y-Z: "as measured by Y")                 (Google / Laszlo Bock) -> warning only
Exit code 1 if any hard check fails.
"""
import re, sys, subprocess, zipfile

BANNED = ["leverage", "leveraged", "leveraging", "spearhead", "spearheaded", "orchestrate", "orchestrated",
          "synergy", "synergies", "dynamic", "passionate", "results-driven", "cutting-edge", "go-getter",
          "detail-oriented", "team player", "utilize", "utilized", "seamlessly", "robust"]

def pdf_lines(pdf):
    return subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout.splitlines()

def bullets(lines):
    out, cur = [], None
    for ln in lines:
        s = ln.rstrip()
        m = re.match(r"^(\s*)•\s+(.*)$", s)
        if m:
            if cur: out.append(cur)
            cur = {"indent": len(m.group(1)), "lines": [m.group(2).strip()]}
        elif cur and s.strip() and len(s) - len(s.lstrip()) > cur["indent"]:
            cur["lines"].append(s.strip())
        else:
            if cur: out.append(cur); cur = None
    if cur: out.append(cur)
    return out

def check(docx):
    bad, warn = [], []
    pdf = docx[:-5] + ".pdf"
    pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    if pages != 1: bad.append(f"{pages} pages")
    xml = zipfile.ZipFile(docx).read("word/document.xml").decode("utf8")
    m = re.search(r"<w:pgMar ([^>]*)/>", xml)
    if m:
        for side in ("top", "bottom", "left", "right"):
            v = int(re.search(rf'w:{side}="(\d+)"', m.group(1)).group(1))
            if v < 720: bad.append(f"margin {side} {v/1440:.2f}in < 0.5in")
    text = " ".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", xml)).lower()
    for w in BANNED:
        if re.search(rf"\b{re.escape(w)}\b", text): bad.append(f"banned word: {w}")
    for b in bullets(pdf_lines(pdf)):
        full = " ".join(b["lines"])
        if len(b["lines"]) > 2: bad.append(f"{len(b['lines'])} lines: {full[:70]}…")
        if len(b["lines"]) > 1 and len(b["lines"][-1].split()) == 1: bad.append(f"one-word last line '{b['lines'][-1]}': {full[:60]}…")
        if not re.search(r"\d", full) and not full.startswith("Courses:"): warn.append(f"no number: {full[:70]}…")
    return bad, warn

rc = 0
for f in sys.argv[1:]:
    bad, warn = check(f)
    print(("FAIL " if bad else "ok   ") + f.split("/")[-1])
    for x in bad: print("   ✗", x)
    for x in warn: print("   ·", x)
    rc |= bool(bad)
sys.exit(rc)
