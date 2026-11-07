#!/usr/bin/env node
// Eligibility gate, step 2: apply the rules in eligibility_rules.js to every fetched job description.
// Usage: node eligibility_classify.js jds.jsonl gate_results.json
// Output: { "<row id>": { v: Eligible|Review|Ineligible|Closed|Unverified, c: "CODE,CODE", e: "evidence", key } }
const fs = require("fs"), path = require("path");
const ELIG = require(path.join(__dirname, "eligibility_rules.js"));
try { ELIG.setCandidate(require(path.join(__dirname, "..", "..", "..", "config", "profile.js")).eligibility || {}); }   // JSA-081
catch (e) { console.error("eligibility: no profile (" + e.message + ") — default candidate"); }
const [src, out] = process.argv.slice(2);
const res = {}, counts = {};
for (const line of fs.readFileSync(src, "utf8").split("\n")) {
  if (!line.trim()) continue;
  const x = JSON.parse(line);
  let r;
  // schema.org validThrough is often just "posted + 30 days" (Built In), so a passed date is a hint, not proof
  if (x.status === "closed" && /validThrough/.test(x.why || "")) r = { v: "Review", c: "POSSIBLY_EXPIRED", e: x.why };
  else if (x.status === "closed") r = { v: "Closed", c: "CLOSED", e: x.why || "" };
  else if (x.status !== "ok") r = { v: "Unverified", c: "UNREADABLE", e: x.why || "" };
  else {
    const c = ELIG.classify({ title: x.title, text: x.text, loc: x.loc, level: x.level });
    const top = c.reasons.filter(q => q.level === "block").concat(c.reasons.filter(q => q.level === "review"));
    r = { v: c.verdict, c: c.reasons.map(q => q.code).join(","), e: top.length ? top[0].ev.replace(/\s+/g, " ").slice(0, 180) : "" };
  }
  r.key = x.key; res[x.id] = r; counts[r.v] = (counts[r.v] || 0) + 1;
}
fs.writeFileSync(out, JSON.stringify(res));
console.log(JSON.stringify(counts));
