#!/usr/bin/env python3
"""
Weekly-Recap Sender (PupShape)

Fires Sunday morning (server-side) for any user with ≥ 1 weight log in
the past 14 days. Builds a personalised one-screen recap: delta this
week vs last, the change vs goal, and a one-line takeaway ("on track" /
"plateau detected" / "off pace — and what we mixed up").

State cache: cache/weekly_recap_state.json keyed by (uid, ISO week)
so each user gets at most one recap per ISO week.
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from pupshape_users_loader import (
    get_access_token, load_all_users, load_dog_weight_logs, is_paid,
)
from pupshape_template_translator import get_localized
from pupshape_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'weekly_recap'
DEEP_LINK = 'pupshape://journey'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'weekly_recap_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': "{{dog_name}}'s week — {{delta_str}}",
    'body': [
        "{{first_name}}, here's the seven-day picture for {{dog_name}}.",
        "Net change this week: {{delta_str}}. {{takeaway}}",
        "{{progress_line}} — that's the line that matters. The graph in-app shows the same number with the full curve underneath, so you can see whether it's a steady slope or a sawtooth.",
        "P.S. One weigh-in this week keeps the engine sharp. Two is even better. Same scale, same time, before breakfast.",
    ],
    'cta': "See {{dog_name}}'s week",
}


def _ref(email: str) -> str:
    h = hashlib.sha256(f"{_REF_SALT}::{email.lower()}".encode()).hexdigest()
    return h[:16]


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {'weeks': {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _iso_week_key() -> str:
    now = datetime.now(timezone.utc)
    yr, wk, _ = now.isocalendar()
    return f"{yr}-W{wk:02d}"


def _summarise(logs: list) -> tuple:
    """Returns (delta_kg_str, takeaway, progress_line). logs is list of
    weight_log dicts sorted ascending by timestamp."""
    if len(logs) < 2:
        return ('first week — no delta yet',
                'Velocity unlocks at weigh-in #2.',
                'One anchor on the curve so far')
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    recent = [l for l in logs if _ts(l.get('logged_at')) and _ts(l['logged_at']) >= cutoff] or [logs[-1]]
    earliest = logs[0]
    latest = logs[-1]
    delta = float(latest.get('weight', 0)) - float(recent[0].get('weight', latest.get('weight', 0)))
    if abs(delta) < 0.05:
        delta_str = 'held steady'
        takeaway = "Holding is its own kind of progress when the trend was going the wrong way."
    elif delta < 0:
        delta_str = f"down {abs(delta):.2f} kg"
        takeaway = "On the right side of the line. The plan keeps the deficit small enough to be sustainable."
    else:
        delta_str = f"up {delta:.2f} kg"
        takeaway = "The plan over-shot this week — likely a treat-creep week. The engine will tighten on the next refresh."
    overall = float(latest.get('weight', 0)) - float(earliest.get('weight', 0))
    progress_line = (f"Overall: {overall:+.2f} kg since first weigh-in"
                     if abs(overall) >= 0.05 else "Holding from baseline")
    return (delta_str, takeaway, progress_line)


def _ts(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        s = str(v).replace('Z', '+00:00')
        return datetime.fromisoformat(s)
    except Exception:
        return None


def main(dry_run: bool = False) -> None:
    print(f"\n📊 Running {KIND}_sender (dry_run={dry_run})…")
    token = get_access_token()
    if not token:
        print("   ⚠️ no token — skipping")
        return

    users = list(load_all_users(token))
    state = _load_state()
    state.setdefault('weeks', {})
    week_key = _iso_week_key()
    sent_this_week = set(state['weeks'].get(week_key, []))

    candidates = []
    for user in users:
        uid = user.get('uid')
        if not uid or not user.get('email'):
            continue
        if uid in sent_this_week:
            continue
        dogs = user.get('dogs', [])
        for dog in dogs:
            logs = load_dog_weight_logs(token, uid, dog.get('dog_id', ''))
            if not logs:
                continue
            logs.sort(key=lambda l: _ts(l.get('logged_at')) or datetime.min.replace(tzinfo=timezone.utc))
            cutoff = datetime.now(timezone.utc) - timedelta(days=14)
            recent = [l for l in logs if (_ts(l.get('logged_at')) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]
            if not recent:
                continue
            candidates.append((user, dog, logs))
            break  # one recap per user, lead dog

    if not candidates:
        print('   ✅ No weekly-recap candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} recaps")
        for u, d, _ in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  {u.get('language','en')}")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, logs in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        delta_str, takeaway, progress_line = _summarise(logs)
        ctx = {
            'first_name':    user.get('first_name', ''),
            'dog_name':      dog.get('name', 'your pup'),
            'delta_str':     delta_str,
            'takeaway':      takeaway,
            'progress_line': progress_line,
        }
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCE['cta']), ctx)
        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='calm', celebratory=False,
            dog_image_url=dog.get('image_url') or '',
            dog_name=dog.get('name', ''),
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            sent_this_week.add(user['uid'])
            if sent % 10 == 0:
                state['weeks'][week_key] = list(sent_this_week)
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  ({dog.get("name","?")})  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    state['weeks'][week_key] = list(sent_this_week)
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
