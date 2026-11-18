// JSA-277: which saved qa entries (config/profile.json → qa) catch the same question — the same matching as qaFindAll in
// answer_rules.js (loaded from it, so the two never drift). Used by qa_add.py before it saves an entry, and by
// `qa_add.py --check-overlaps` over the whole table.
//   JSA_PROFILE=<profile.json> node qa_overlap.js --all        → [{n, q, entries: [n, …]}]  every entry whose own question 2+ entries catch
//   JSA_PROFILE=<profile.json> node qa_overlap.js --entry N [--options "a|b"]
//        → {catches_it: [n…], it_catches: [n…]}  entry N against the others. With --options (the form field's option list; "" = a
//        text box) an older entry that catches the question but gives no answer on that shape does not count (JSA-333).
const path = require('path');
const { qaFindAll, qaOne, QA } = require(path.join(__dirname, 'answer_rules.js'));
const brief = e => ({ n: e.n, q: e.q, match: e.match || '', answer: e.text !== undefined ? e.text : (e.yes === undefined ? '' : (e.yes ? 'Yes' : 'No')),
  added: e.added || '', source: e.source || '' });
const args = process.argv.slice(2);
let out;
const oi = args.indexOf('--options'), shape = oi < 0 ? null : args[oi + 1].split('|').map(x => x.trim()).filter(Boolean);
const answersShape = (e, label) => { const a = qaOne(e, { o: shape, t: shape.length === 1 ? 'checkbox' : shape.length ? 'combo' : 'text' }, label); return !!a && a.status === 'ok'; };   // would this entry answer the field?
if (args[0] === '--entry') {
  const n = Number(args[1]), me = QA.find(e => e.n === n);
  if (!me) { process.stderr.write('qa_overlap: no entry #' + n + '\n'); process.exit(2); }
  out = { entry: brief(me),
    catches_it: qaFindAll(me.q).filter(e => e.n !== n && (shape === null || answersShape(e, me.q))).map(brief),                                  // older entries that also answer the new question
    it_catches: QA.filter(e => e.n !== n && e.q && qaFindAll(e.q).some(x => x.n === n)).map(brief) };   // other entries' questions the new one would answer too
} else {
  out = QA.filter(b => b.q).map(b => ({ n: b.n, q: b.q, entries: qaFindAll(b.q).map(brief) })).filter(o => o.entries.length > 1);
}
process.stdout.write(JSON.stringify(out));
