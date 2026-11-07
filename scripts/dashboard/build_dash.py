"""Local Job Hunt Command Center (ADR-0004, JSA-029): the claude.ai page, fed from data/store/ instead of claude.ai.

Wraps skills/job-hunt-pipeline/scripts/dashboard_index.html (the same page code claude.ai serves) with
  - a small `dash` shim (calc / data / onData / setLink) that answers from the embedded store data,
  - the CSS variables the claude.ai runtime used to provide (light + dark),
  - vendored d3 (no network needed),
and writes dashboard/index.html plus dashboard/stamp.js (both git-ignored build output).
An open tab loads stamp.js every 20 s and reloads itself only when the data changed (the open tab is kept via #hash).

usage:
  python3 scripts/dashboard/build_dash.py           rebuild now
  python3 scripts/dashboard/build_dash.py --check   exit 0 = current, 1 = stale (the LaunchAgent runs this first)
"""
import hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import store  # noqa: E402

PAGE = os.path.join(ROOT, "skills", "job-hunt-pipeline", "scripts", "dashboard_index.html")
D3 = os.path.join(HERE, "vendor", "d3.v7.9.0.min.js")
sys.path.insert(0, os.path.join(ROOT, "config"))
import paths as jpaths  # noqa: E402  (ADR-0008: the page is using-system output → the data home)
OUT = jpaths.at("dashboard")

CSS = """
:root{--font-anthropic-sans:-apple-system,BlinkMacSystemFont,"Helvetica Neue","PingFang SC",sans-serif;
--font-anthropic-serif:"Iowan Old Style","Charter",Georgia,"Songti SC",serif;
--cds-font-size-caption:12px;--cds-font-size-body:14px;--cds-font-size-heading:17px;--cds-font-size-title:28px;
--cds-font-weight-medium:550;--cds-radius:8px;--cds-gap-xs:4px;--cds-gap-sm:8px;--cds-gap-md:14px;--cds-gap-lg:22px;
--cds-pad-xs:4px;--cds-pad-sm:8px;--cds-pad-md:12px;--cds-pad-lg:18px;--cds-dur-slow:.3s;
--color-bg:#faf9f5;--color-panel:#ffffff;--color-fg:#1f1e1d;--color-fg-muted:#6b6a65;--color-border-line:#e3e1d9;
--cds-border:1px solid #e3e1d9;--color-ok:#2f7d4f;--color-warn:#a5640c;--color-bad:#b3362d;
--cds-chart-muted:#c9c6bb;--cds-chart-axis:#8a887f;--cds-chart-status-critical:#b3362d;--cds-text-secondary:#6b6a65;
--cds-surface-popover:#ffffff;--cds-shadow-popover:0 6px 24px rgba(0,0,0,.14)}
@media (prefers-color-scheme:dark){:root{--color-bg:#1f1e1d;--color-panel:#2a2927;--color-fg:#eeece4;--color-fg-muted:#a9a69c;
--color-border-line:#3d3b37;--cds-border:1px solid #3d3b37;--color-ok:#6cc08b;--color-warn:#e0a54a;--color-bad:#ec7a70;
--cds-chart-muted:#55524c;--cds-chart-axis:#8f8c83;--cds-chart-status-critical:#ec7a70;--cds-text-secondary:#a9a69c;
--cds-surface-popover:#2f2e2b;--cds-shadow-popover:0 6px 24px rgba(0,0,0,.5)}}
html,body{margin:0;background:var(--color-bg);color:var(--color-fg);font-family:var(--font-anthropic-sans);font-size:var(--cds-font-size-body)}
#dash-root{max-width:1400px;margin:0 auto;padding:24px 28px 60px}
#dash-root a{color:inherit}
.local-bar{font-size:12px;color:var(--color-fg-muted);margin-bottom:10px}
"""

SHIM = """
window.dash = (function () {
  const D = window.__STORE, calcs = {}, memo = {}, subs = [];
  return {
    // categorical series colours (the claude.ai runtime provided these as dash.colors)
    colors: ['#c15f3c', '#3d6fa8', '#5e9a5a', '#b08a2e', '#8a5aa6', '#4f9a9a'],
    calc(name, spec) { calcs[name] = spec; delete memo[name]; },
    data(name) {
      if (name in D) return { status: 'ok', data: D[name] };
      const c = calcs[name];
      if (!c) return { status: 'error', data: [] };
      if (!(name in memo)) memo[name] = c.fn(...c.inputs.map((i) => this.data(i).data));
      return { status: 'ok', data: memo[name] };
    },
    onData(cb) { subs.push(cb); setTimeout(cb, 0); },
    setLink(id) { history.replaceState(null, '', '#' + id); },
  };
})();
"""

WATCHER = """
(function () {
  const mine = window.__STAMP;
  setInterval(() => {
    const s = document.createElement('script');
    s.src = 'stamp.js?' + Date.now();
    s.onload = () => { s.remove(); if (window.__STAMP_NOW && window.__STAMP_NOW !== mine) location.reload(); };
    s.onerror = () => s.remove();
    document.head.appendChild(s);
  }, 20000);
})();
"""


def fingerprint():
    h = hashlib.sha256()
    ledgers = [jpaths.data("runner", n) for n in ("queue.md", "human_checks.jsonl", "apply_requests.jsonl", "results.jsonl")]   # JSA-189
    for p in [PAGE, D3, __file__, os.path.join(ROOT, "scripts", "platform_counts.py"), os.path.join(ROOT, "scripts", "store", "joey_todo.py")] + [store.path(n) for n in store.DATASETS] + ledgers:
        if os.path.exists(p):
            h.update(f"{p}:{os.path.getmtime(p)}:{os.path.getsize(p)}".encode())
    return h.hexdigest()[:16]


def build():
    data = {n: store.load(n) for n in store.DATASETS}
    import platform_counts as PC                                  # Runner column (JSA-177): platform + runner status, page data only
    data["jobs"] = [{**j, **PC.runner_fields(j)} for j in data.get("jobs") or []]
    try:                                                          # Joey's to-do: one row per application waiting for him (JSA-189)
        import joey_todo
        data["joey_todo"] = joey_todo.build()
    except Exception as e:
        print(f"joey_todo skipped: {type(e).__name__}: {e}")
        data["joey_todo"] = []
    stamp = fingerprint()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    built = time.strftime("%Y-%m-%d %H:%M")
    counts = " · ".join(f"{n} {len(v)}" for n, v in data.items())
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Job Hunt Command Center (local)</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<style>{CSS}</style><script>{open(D3, encoding='utf-8').read()}</script>"
        f"<script>window.__STAMP={json.dumps(stamp)};window.__STORE={blob};</script><script>{SHIM}</script>"
        f"</head><body><div id='dash-root'><div class='local-bar'>Local · data/store · built {built} · {counts}</div>"
        f"{open(PAGE, encoding='utf-8').read()}</div><script>{WATCHER}</script></body></html>"
    )
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, ".index.html.tmp")
    open(tmp, "w", encoding="utf-8").write(html)
    os.replace(tmp, os.path.join(OUT, "index.html"))
    open(os.path.join(OUT, "stamp.js"), "w").write(f"window.__STAMP_NOW={json.dumps(stamp)};\n")
    print(f"built dashboard/index.html ({len(html) // 1024} KB) · {counts}")


def current():
    p = os.path.join(OUT, "stamp.js")
    return os.path.exists(p) and fingerprint() in open(p).read()


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if current() else 1)
    build()
