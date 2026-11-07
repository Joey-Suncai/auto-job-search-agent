"""When a runner's tab stays open after the run (Joey 2026-11-05 「目前标签页里还有太多的标签，以后干跑结束也要把标签关掉」).

Pure (tested). A run's page is closed when the run ends — dry run, blocked, needs-user, failed, unconfirmed, a login that
timed out, a stop mid-wizard — because a stopped run is always retried FRESH later (new tab) and its evidence is already
in run_log.md, form_check.json and the screenshots. The only page kept open is one a person is about to act in right now:
a CAPTCHA / human check parked for Joey. `--keep-tab` (Joey works in the page himself) still overrides.
"""
KEEP = ('captcha',)


def keep_open(status, keep_tab=False):
    """True = leave this run's tab open."""
    return bool(keep_tab) or str(status or '').strip().lower() in KEEP
