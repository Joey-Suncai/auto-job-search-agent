#!/usr/bin/env python3
"""Re-match every company's H-1B facts and merge alias company rows (JSA-098).

Uses skills/job-hunt-pipeline/scripts/h1b_match.py (the matcher build_jobs / append_new use). Changes only the
company-fact fields — jobs: h1b_fy25, h1b_total, h1b_since and sponsorship when it is one of the three H-1B labels
(a posting's own "Blocked: …" / "Posting offers sponsorship" stays); companies: the same facts, plus one row per
employer (group_key) with the counts added up. store.save("jobs") re-scores, so tier follows the new sponsorship.
Spec: scripts/test_cases/h1b_match_spec.md (section "Store fix").

    python3 scripts/store/fix_company_h1b.py --src <dir with the two cloned H-1B repos>          # report only
    python3 scripts/store/fix_company_h1b.py --src <dir> --write                                 # write the store
Without --src the two public data repos are cloned (data only, nothing executed) into a temp folder.
"""
import json, os, subprocess, sys, tempfile, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "skills", "job-hunt-pipeline", "scripts"))
import h1b_match as M  # noqa: E402

COUNTS = ("open_roles", "internships", "new_grad", "a_roles")


def facts(h):
    return {"h1b_fy25": h["fy25"] or 0, "h1b_total": h["total"] or 0, "h1b_since": h["first"] or ""}


def refresh(row, h):
    """row with its H-1B facts from h (an H1B.lookup result); a posting-level sponsorship label is kept."""
    out = dict(row, **facts(h))
    if out.get("sponsorship") in (None, "") or out.get("sponsorship") in M.H1B_LABELS:
        out["sponsorship"] = M.sponsor_label(h)
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return -1.0


def merge_companies(rows, H):
    """One row per employer: rows with the same group_key merge (unless the names are in M.NOT_SAME); the row with the
    most open_roles keeps its name (tie: the shorter name, then alphabetical). Counts add up; best_* come from the row
    with the highest best_score; gc_* from the row with the most gc_perm; referral / contacts / warm_path from the kept
    row, else the first other row that has them. Then every row gets refresh(). Returns (rows, {kept: [merged names]})."""
    groups = collections.OrderedDict()
    for r in rows:
        groups.setdefault(M.group_key(r["company"]), []).append(r)
    out, merged = [], {}
    for g in groups.values():
        parts = [g]
        names = {r["company"] for r in g}
        if any(pair <= names for pair in M.NOT_SAME):
            parts = [[r] for r in g]
        for p in parts:
            p = sorted(p, key=lambda r: (-(_num(r.get("open_roles")) if r.get("open_roles") is not None else 0),
                                         len(r["company"]), r["company"]))
            keep = dict(p[0])
            if len(p) > 1:
                for k in COUNTS:
                    if any(k in r for r in p):
                        keep[k] = sum(int(_num(r.get(k)) if _num(r.get(k)) > 0 else 0) for r in p)
                best = max(p, key=lambda r: _num(r.get("best_score")))
                for k in ("best_score", "best_role", "best_tier"):
                    if k in best:
                        keep[k] = best[k]
                gc = max(p, key=lambda r: _num(r.get("gc_perm")))
                for k in ("gc_sponsor", "gc_perm", "gc_months"):
                    if k in gc:
                        keep[k] = gc[k]
                for k in ("referral", "contacts", "warm_path"):
                    if keep.get(k) in (None, "", "Cold"):
                        v = next((r[k] for r in p[1:] if r.get(k) not in (None, "", "Cold")), None)
                        if v is not None:
                            keep[k] = v
                tr = []
                for r in p:
                    tr += [t for t in str(r.get("tracks") or "").split("; ") if t and t not in tr]
                if tr:
                    keep["tracks"] = "; ".join(tr)
                merged[keep["company"]] = [r["company"] for r in p[1:]]
            out.append(refresh(keep, H.lookup(keep["company"])))
    return out, merged


def _clone(dst):
    for r in ("flexapply/companies-that-sponsor-h1b", "sergyinfo/h1b-open-data"):
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{r}", f"{dst}/{r.replace('/', '_')}"],
                       check=True, timeout=600)
    return dst


def main(a):
    import store
    src = a[a.index("--src") + 1] if "--src" in a else _clone(tempfile.mkdtemp(prefix="h1b_src_"))
    H = M.H1B(M.records_from(src))
    if not H.emp:
        print("no H-1B data under", src); return 1
    comps = store.load("companies")
    new_c, merged = merge_companies(comps, H)
    print(f"companies {len(comps)} -> {len(new_c)} · merged groups {len(merged)}")
    for k, v in sorted(merged.items()):
        print(f"  {k}  <-  {', '.join(v)}")
    old_by = {r["company"]: r for r in comps}
    changed_c = [r for r in new_c if any(old_by.get(r["company"], {}).get(k) != r.get(k)
                                         for k in ("h1b_fy25", "h1b_total", "h1b_since", "sponsorship"))]
    print(f"company rows with new facts: {len(changed_c)}")
    jobs = store.load("jobs")            # loaded right before the save: other sessions write the store too
    new_j = [refresh(j, H.lookup(j["company"])) for j in jobs]
    sp = sum(o.get("sponsorship") != n.get("sponsorship") for o, n in zip(jobs, new_j))
    fx = sum(any(o.get(k) != n.get(k) for k in ("h1b_fy25", "h1b_total", "h1b_since")) for o, n in zip(jobs, new_j))
    print(f"jobs {len(jobs)} · facts changed {fx} · sponsorship level changed {sp}")
    print("sponsorship moves:", dict(collections.Counter(f"{o.get('sponsorship')} -> {n['sponsorship']}"
                                                         for o, n in zip(jobs, new_j) if o.get("sponsorship") != n["sponsorship"])))
    if "--write" not in a:
        print("(report only; --write to save)"); return 0
    store.save("companies", new_c)
    before = {j["id"]: j.get("tier") for j in jobs}
    store.save("jobs", new_j)
    after = store.load("jobs")
    moves = collections.Counter(f"{before.get(j['id'])} -> {j.get('tier')}" for j in after if before.get(j["id"]) != j.get("tier"))
    print(f"saved · tier changed {sum(moves.values())}: {dict(moves)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
