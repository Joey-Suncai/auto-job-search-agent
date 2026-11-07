#!/usr/bin/env python3
"""One-off probe: download a few sample job pages / API answers from sites the gate can't read yet, so readers can be
written against real responses. Saves raw files to data/processed/probe/ and an index.json with status codes.
Usage (from skills/job-hunt-pipeline/scripts): python3 probe_sites.py ../../../data/dashboard/dash_jobs_for_gate.json ../../../data/processed/probe
"""
import json, os, re, sys, urllib.error, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
try:
    import ssl, certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = None


def get(url, accept="text/html,application/json;q=0.9,*/*;q=0.8", data=None, headers=None):
    try:
        req = urllib.request.Request(url, headers={**UA, "Accept": accept, **(headers or {})}, data=data)
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body, url
    except Exception as e:
        return 0, str(e), url


GROUPS = {
    "tiktok": r"lifeattiktok\.com/search/(\d+)",
    "bytedance": r"jobs\.bytedance\.com/.*position/(\d+)",
    "amazon": r"amazon\.jobs/.*jobs/(\d+)",
    "oracle": r"(\w[\w-]*\.fa\.[\w.]*oraclecloud\.com)/hcmUI/CandidateExperience/[a-z]{2}/sites/([\w-]+)/(?:job|requisitions/preview)/(\d+)",
    "workable": r"apply\.workable\.com/([\w-]+)/j/(\w+)",
    "zapply": r"zapply\.jobs/",
    "vansh": r"go\.vansh\.nyc/",
    "rippling": r"ats\.rippling\.com/",
}


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    rows = json.load(open(src))
    idx = []
    for g, pat in GROUPS.items():
        samples = [r for r in rows if re.search(pat, r.get("url") or "")][:2]
        for n, r in enumerate(samples):
            u = r["url"]; m = re.search(pat, u)
            tries = [("page", u, None, None)]
            if g == "oracle":
                host, site, rid = m.group(1), m.group(2), m.group(3)
                q = urllib.parse.quote(f'ById;Id="{rid}",siteNumber={site}', safe=';=",')
                tries.append(("rest", f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder={q}", None, None))
            if g == "workable":
                tries.append(("api", f"https://apply.workable.com/api/v2/accounts/{m.group(1)}/jobs/{m.group(2)}", None, None))
            if g == "amazon":
                tries.append(("json", f"https://www.amazon.jobs/en/jobs/{m.group(1)}.json", None, None))
            if g == "bytedance":
                tries.append(("api", f"https://jobs.bytedance.com/api/v1/job/posts/{m.group(1)}?portal_type=2&with_recommend=false", None, {"Accept": "application/json", "portal-channel": "official", "portal-platform": "pc", "website-path": "en"}))
            if g == "tiktok":
                tries.append(("api", f"https://api.lifeattiktok.com/api/v1/public/supplier/job/posts/{m.group(1)}?portal_type=4", None, {"Accept": "application/json", "website-path": "tiktok"}))
            for kind, url, data, hdr in tries:
                s, body, final = get(url, data=data, headers=hdr)
                ext = "json" if body.lstrip().startswith(("{", "[")) else "html"
                fn = f"{g}_{n}_{kind}.{ext}"
                open(os.path.join(out, fn), "w").write(body)
                idx.append({"group": g, "id": r["id"], "kind": kind, "url": url, "status": s, "final_url": final, "bytes": len(body), "file": fn})
                print(f"{g:10} {kind:5} {s} {len(body):>8} bytes  {final[:90]}")
    json.dump(idx, open(os.path.join(out, "index.json"), "w"), indent=1)
    print("saved to", out)


if __name__ == "__main__":
    main()
