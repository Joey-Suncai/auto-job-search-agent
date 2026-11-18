"""Local data store for the job-search agent (ADR-0004): the one place every harness reads and writes.

data/store/ holds one file per dataset. Row datasets are JSONL (one object per line, sorted by key) so a daily run
changes only the rows it touched; derived per-run fields (jobs `rank`) are not stored and are recomputed on load.

usage:
  python3 scripts/store/store.py --check                 counts + schema check (exit 1 on a problem)
  python3 scripts/store/store.py --export jobs out.json  write a dataset as one JSON array (rank included for jobs)
  python3 scripts/store/store.py --import jobs in.json   replace a dataset from a JSON array (checked first)
"""
import json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
STORE = os.environ.get("JOB_STORE_DIR", jpaths.data("store"))

# name -> (file, key field, fields that must be present, derived fields never stored)
DATASETS = {
    "jobs":         ("jobs.jsonl",         "id",      ["id", "company", "title", "score"], ["rank"]),
    "applications": ("applications.jsonl", "job_id",  ["job_id", "company", "title", "status"], []),
    "emails":       ("emails.jsonl",       "id",      ["id", "date", "company"], []),
    "companies":    ("companies.jsonl",    "company", ["company"], []),
    "contacts":     ("contacts.jsonl",     "key",     ["key", "person", "company"], []),
    "sources":      ("sources.jsonl",      "source",  ["source"], []),
}


def path(name):
    return os.path.join(STORE, DATASETS[name][0])


def problems(name, rows):
    """Every reason these rows must not be written; empty list = ok."""
    _, key, required, _ = DATASETS[name]
    out, seen = [], set()
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            out.append(f"{name} row {i}: not an object")
            continue
        miss = [f for f in required if r.get(f) in (None, "")]
        if miss:
            out.append(f"{name} row {i}: missing {miss}")
        k = r.get(key)
        if k in seen:
            out.append(f"{name}: duplicate {key} {k}")
        seen.add(k)
    return out


def with_rank(rows):
    # same order append_new.py uses (score high -> low); ties broken by id so the result is stable
    for i, j in enumerate(sorted(rows, key=lambda x: (-(x.get("score") or 0), x["id"]))):
        j["rank"] = i + 1
    return rows


def load(name):
    p = path(name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return with_rank(rows) if name == "jobs" else rows


def save(name, rows):
    """Check, strip derived fields, sort by key, write atomically. Raises ValueError and writes nothing on a problem."""
    if name == "jobs":   # every writer's rows arrive with the dashboard fields filled (JSA-095; fills only what is missing)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import complete_jobs
        rows = complete_jobs.complete(rows, complete_jobs.load_companies(STORE))
        # ... and scored by the v2 rules before they reach the dashboard (JSA-096, Joey 2026-11-02:
        # 「以后新获得的职位都需要用规则算过分之后再接入 dashboard」)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scoring"))
        import score_v2
        rows = score_v2.score_rows(rows)
    bad = problems(name, rows)
    if bad:
        raise ValueError("; ".join(bad[:5]) + (f" (+{len(bad) - 5} more)" if len(bad) > 5 else ""))
    _, key, _, derived = DATASETS[name]
    clean = [{k: v for k, v in r.items() if k not in derived} for r in rows]
    clean.sort(key=lambda r: str(r[key]))
    os.makedirs(STORE, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STORE, prefix=f".{name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in clean:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path(name))
    try:                                                         # JSA-358: the writer commits its own file on the spot (best effort)
        import data_git
        data_git.commit_paths([path(name)], f"data: {name} ({len(clean)} rows)")
    except Exception:                                            # noqa: BLE001 — a data write never fails because of git
        pass
    return len(clean)


def check():
    report, bad = {}, []
    for name in DATASETS:
        rows = load(name)
        report[name] = len(rows)
        bad += problems(name, rows)
    return report, bad


def main(a):
    if "--check" in a:
        report, bad = check()
        print("store: " + " · ".join(f"{k} {v}" for k, v in report.items()))
        for b in bad[:20]:
            print("PROBLEM:", b)
        return 1 if bad else 0
    if "--export" in a:
        name, out = a[a.index("--export") + 1], a[a.index("--export") + 2]
        json.dump(load(name), open(out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"exported {name} -> {out}")
        return 0
    if "--import" in a:
        name, src = a[a.index("--import") + 1], a[a.index("--import") + 2]
        n = save(name, json.load(open(src, encoding="utf-8")))
        print(f"imported {name}: {n} rows")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
