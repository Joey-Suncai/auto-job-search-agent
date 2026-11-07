#!/usr/bin/env python3
"""Pick the next action for a structured failure event (Joey 2026-10-29).

The runner never asks a model "what should I do" in free text. It emits a small, structured event and this
module asks for ONE action out of a fixed menu, validates the answer against policy.json, and logs the decision.

    from decide import decide
    d = decide({"event": "requirement_appeared", "kind": "cover_letter", "required": True,
                "generatable": True, "page": "Application Questions", "evidence": "file slot 'Cover Letter'"}, folder)
    # -> {"action": "generate_material", "reason": "...", "source": "model", "event_hash": "..."}

Guarantees:
  * the returned action is always in the menu for that event (anything else becomes pause_for_joey);
  * a hard rule violated by the model is downgraded the same way (see _valid);
  * the same event is decided once (event_hash), so a re-rendered page cannot generate three letters;
  * at most policy.max_decisions_per_application decisions per folder, then pause_for_joey;
  * every decision is appended to <folder>/decisions.jsonl (event, action, reason, source, model).
"""
import hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY_PATH = os.path.join(os.path.dirname(HERE), 'policy.json')
LOG_NAME = 'decisions.jsonl'
VOLATILE = ('ts', 'timestamp', 'page_url', 'screenshot')


def load_policy(path=POLICY_PATH):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def event_hash(event):
    clean = {k: v for k, v in sorted(event.items()) if k not in VOLATILE}
    return hashlib.sha256(json.dumps(clean, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _menu(policy, event):
    spec = policy['events'].get(event.get('event')) or {}
    return list(spec.get('allowed') or []), spec


def _valid(policy, event, action, spec):
    if action not in (spec.get('allowed') or []):
        return False, 'not in the allowed list'
    if action in ('generate_material', 'regenerate_material') and not event.get('generatable'):
        return False, 'material is not generatable from approved sources'
    if action == 'skip_if_optional' and event.get('required'):
        return False, 'field is required'
    if action == 'classify_and_retry' and int(event.get('retries_used') or 0) >= int(spec.get('max_retries') or 0):
        return False, 'retry budget used up'
    return True, ''


def _read_log(folder):
    path = os.path.join(folder, LOG_NAME) if folder else None
    if not path or not os.path.exists(path):
        return []
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def _append_log(folder, row):
    if not folder:
        return None
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, LOG_NAME)
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    return path


SYSTEM = """You choose the next action for one job-application event. You get a JSON with the event, its evidence,
the requirements already known, the materials already produced, and allowed_actions. Return JSON only:
{"action": "<one of allowed_actions>", "reason": "<one short sentence>"}
Rules:
%s
You never act yourself: a script performs the action afterwards."""


def _ask_model(event, menu, policy, ask):
    payload = {'event': event, 'allowed_actions': menu}
    msg = json.dumps(payload, ensure_ascii=False)
    system = SYSTEM % '\n'.join('- ' + r for r in policy.get('rules') or [])
    return ask(msg, system)


def decide(event, folder=None, ask=None, policy=None, now=None):
    """Return {action, reason, source, event_hash}. Cheap, deterministic-by-default, fully logged."""
    policy = policy or load_policy()
    h = event_hash(event)
    log = _read_log(folder)

    cached = next((r for r in log if r.get('event_hash') == h), None)
    if cached:
        return {'action': cached['action'], 'reason': cached.get('reason', ''), 'source': 'cached', 'event_hash': h}

    cap = int(policy.get('max_decisions_per_application') or 3)
    if len(log) >= cap:
        row = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'event_hash': h, 'event': event.get('event'),
               'action': policy['default_action'], 'reason': 'decision cap reached', 'source': 'cap'}
        _append_log(folder, row)
        return {'action': row['action'], 'reason': row['reason'], 'source': 'cap', 'event_hash': h}

    menu, spec = _menu(policy, event)
    if not menu:
        row = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'event_hash': h, 'event': event.get('event'),
               'action': policy['default_action'], 'reason': 'unknown event type', 'source': 'unknown_event'}
        _append_log(folder, row)
        return {'action': row['action'], 'reason': row['reason'], 'source': 'unknown_event', 'event_hash': h}

    action, reason, source = policy['default_action'], '', 'fallback'
    if ask is not None:
        try:
            reply = _ask_model(event, menu, policy, ask) or {}
            cand = str(reply.get('action') or '').strip()
            ok, why = _valid(policy, event, cand, spec)
            if ok:
                action, reason, source = cand, str(reply.get('reason') or '')[:200], 'model'
            else:
                reason, source = 'model suggested %r (%s)' % (cand, why), 'invalid_action'
        except Exception as exc:
            reason, source = 'model call failed: %s' % type(exc).__name__, 'model_error'
    else:
        reason, source = 'no model configured', 'no_model'

    row = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'event_hash': h, 'event': event.get('event'),
           'action': action, 'reason': reason, 'source': source, 'menu': menu}
    _append_log(folder, row)
    return {'action': action, 'reason': reason, 'source': source, 'event_hash': h}

def deepseek_ask(msg, system):
    """Production caller: DeepSeek picks from the menu (cheap; the menu makes it nearly a classifier)."""
    import ladder
    usage = {'calls': 0, 'prompt': 0, 'out': 0}
    return ladder.ask_deepseek(msg, usage, system)


def main(argv):
    """decide.py <event.json> [folder] [--no-model]  → prints the decision as JSON."""
    if not argv:
        print('usage: decide.py <event.json> [folder] [--no-model]')
        return 2
    event = json.load(open(argv[0], encoding='utf-8'))
    folder = next((a for a in argv[1:] if not a.startswith('--')), None)
    ask = None if '--no-model' in argv else deepseek_ask
    out = decide(event, folder, ask=ask)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
