# cdp_connect — connecting a runner to the job Chrome (spec)

`ensure_tab(cdp, http)` is called before every `connect_over_cdp`. `cdp` is the endpoint URL, e.g. `http://127.0.0.1:9222`.
`http(method, url)` performs one HTTP request to Chrome's DevTools HTTP API and returns the parsed JSON body (a list or
object); it raises `OSError` when Chrome is not reachable.

Problem: Playwright's `connect_over_cdp` fails with "Browser context management is not supported" when the browser has
no open tab (no target of type `page`).

Rules:
1. `ensure_tab` first lists targets with `GET <cdp>/json/list`. A target counts as a tab only when its `type` is `page`.
   Service workers, background pages, extensions and other types do not count.
2. If at least one tab exists, `ensure_tab` changes nothing: it makes no other request and returns `False`.
3. If there is no tab, it opens one with `PUT <cdp>/json/new?about:blank` and returns `True`.
4. The trailing slash of `cdp` is ignored (`http://127.0.0.1:9222/` and `http://127.0.0.1:9222` give the same URLs).
5. If Chrome is not reachable (the listing raises `OSError`), `ensure_tab` does not raise and does not try to open a tab;
   it returns `False` — the later `connect_over_cdp` reports the real error.
6. If the listing is not a list (unexpected answer), it is treated like an unreachable Chrome: no request, returns `False`.
7. If opening the tab raises `OSError`, `ensure_tab` does not raise and returns `False`.
8. An empty list means no tab. A list whose only targets are not `page` also means no tab.
9. `ensure_tab` never closes, navigates or changes an existing tab, and never opens more than one tab per call.
