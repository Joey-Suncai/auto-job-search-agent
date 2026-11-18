"""Connect to the job Chrome over CDP (JSA-386).

Playwright's connect_over_cdp fails with "Browser context management is not supported" when the browser has no open
tab: it needs a page target to attach the default context to. ensure_tab() opens one about:blank tab in that case;
connect() is the one connection point the runners use."""
import json
import urllib.request


def _http(method, url):
    req = urllib.request.Request(url, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # localhost never goes through a proxy
    with opener.open(req, timeout=5) as r:
        return json.loads(r.read().decode('utf-8') or 'null')


def ensure_tab(cdp, http=None):
    """Open an about:blank tab when Chrome has none. True only when a tab was opened; never raises."""
    http = http or _http
    base = cdp.rstrip('/')
    try:
        targets = http('GET', base + '/json/list')
    except (OSError, ValueError):
        return False                       # not reachable: connect_over_cdp reports the real error
    if not isinstance(targets, list):
        return False
    if any(isinstance(t, dict) and t.get('type') == 'page' for t in targets):
        return False
    try:
        http('PUT', base + '/json/new?about:blank')
    except (OSError, ValueError):
        return False
    return True


def connect(pw, cdp, **kw):
    """pw.chromium.connect_over_cdp(cdp) after making sure there is a tab."""
    ensure_tab(cdp)
    return pw.chromium.connect_over_cdp(cdp, **kw)
