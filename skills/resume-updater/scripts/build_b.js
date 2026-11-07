// Style B: modern layout — summary, skills, projects first, maroon accents.
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, TabStopType, BorderStyle, LevelFormat, ExternalHyperlink, AlignmentType } = require('docx');

const C = JSON.parse(fs.readFileSync(path.join(__dirname, 'content.json'), 'utf8'));
const PREFIX = require(path.join(__dirname, '..', '..', '..', 'config', 'profile.js')).name.file_prefix;   // JSA-077
const MAROON = '800000', GRAY = '555555', FONT = 'Calibri';
const RIGHT = 12240 - 2 * 820; // content width in DXA
const SZ = 20; // 10pt

const run = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || SZ, bold: o.bold, italics: o.italics, color: o.color, allCaps: o.caps, characterSpacing: o.spacing });

function section(title) {
  return new Paragraph({
    spacing: { before: 140, after: 50 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: MAROON, space: 1 } },
    children: [run(title, { bold: true, color: MAROON, size: 22, caps: true, spacing: 20 })],
  });
}
const lineRight = (left, right, o = {}) => new Paragraph({
  tabStops: [{ type: TabStopType.RIGHT, position: RIGHT }],
  spacing: { before: o.before || 60, after: 10 },
  keepNext: true,
  children: [...left, new TextRun({ text: '\t', font: FONT, size: SZ }), run(right, { bold: true, color: GRAY })],
});
const bullet = (t) => new Paragraph({ numbering: { reference: 'b', level: 0 }, spacing: { after: 15 }, children: [run(t)] });

function buildDoc(key, r) {
  const drop = new Set(r.drop_b || []);
  const strip = (xs) => xs.map(x => ({ ...x, bullets: x.bullets.filter(b => !drop.has(b)) }));
  r = { ...r, projects: strip(r.projects), exp: strip(r.exp) };
  const kids = [];
  kids.push(new Paragraph({ spacing: { after: 0 }, children: [run(C.NAME, { bold: true, size: 40, color: MAROON })] }));
  kids.push(new Paragraph({ spacing: { after: 40 }, children: [run(r.label + ' · 2027 Internship', { size: 22, color: GRAY, caps: true, spacing: 30, bold: true })] }));
  const parts = C.CONTACT.split(' | ');
  const contactKids = [];
  parts.forEach((p, i) => {
    if (i) contactKids.push(run('  |  ', { color: MAROON }));
    if (p.startsWith('linkedin') || p.startsWith('github')) {
      contactKids.push(new ExternalHyperlink({ link: 'https://' + p, children: [run(p, { color: '1F3864' })] }));
    } else contactKids.push(run(p));
  });
  kids.push(new Paragraph({ spacing: { after: 40 }, children: contactKids }));

  kids.push(section('Summary'));
  kids.push(new Paragraph({ spacing: { after: 20 }, children: [run(r.summary)] }));

  kids.push(section('Skills'));
  r.skills.forEach(([k, v]) => kids.push(new Paragraph({ spacing: { after: 15 }, children: [run(k + ': ', { bold: true }), run(v)] })));

  kids.push(section('Projects'));
  r.projects.forEach((p, i) => {
    kids.push(lineRight([run(p.title, { bold: true }), run('  ·  ' + p.tag, { italics: true, color: GRAY })], p.date, { before: i ? 70 : 30 }));
    p.bullets.forEach(b => kids.push(bullet(b)));
  });

  kids.push(section('Experience'));
  r.exp.forEach((j, i) => {
    kids.push(lineRight([run(j.title, { bold: true }), run('  ·  ' + j.org, { bold: true, color: MAROON })], j.date, { before: i ? 70 : 30 }));
    j.bullets.forEach(b => kids.push(bullet(b)));
  });

  kids.push(section('Education'));
  C.EDU.forEach((e, i) => {
    kids.push(lineRight([run(e.school, { bold: true }), run('  ·  ' + e.loc, { color: GRAY })], e.date, { before: i ? 60 : 30 }));
    kids.push(new Paragraph({ spacing: { after: 10 }, children: [run(e.degree + e.detail, { italics: true }), run('  —  Courses: ' + e.courses, { color: GRAY })] }));
  });

  kids.push(section('Leadership'));
  kids.push(lineRight([run(C.LEAD.title, { bold: true }), run('  ·  ' + C.LEAD.org, { bold: true, color: MAROON })], C.LEAD.date, { before: 30 }));
  ((r.lead_short_b ?? r.lead_short) ? C.LEAD.bullets_short : C.LEAD.bullets_full).forEach(b => kids.push(bullet(b)));

  return new Document({
    creator: C.NAME, title: `${C.NAME} — ${r.label} Resume`,
    styles: { default: { document: { run: { font: FONT, size: SZ } } } },
    numbering: { config: [{ reference: 'b', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 300, hanging: 200 } }, run: { color: MAROON } } }] }] },
    sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 640, bottom: 640, left: 820, right: 820 } } }, children: kids }],
  });
}

(async () => {
  for (const [key, r] of Object.entries(C.ROLES)) {
    const fn = path.join(__dirname, 'out', `${PREFIX}_Resume_${key}_B-Modern.docx`);
    fs.writeFileSync(fn, await Packer.toBuffer(buildDoc(key, r)));
    console.log(fn);
  }
})();
