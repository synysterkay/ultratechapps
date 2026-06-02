#!/usr/bin/env python3
"""
Body-Check-Reminder Sender (PupShape)

Fires when a user hasn't completed a body-condition-score (BCS) task in
any of their dogs' task_completions for 28+ days. BCS is the
qualitative signal the scale can't give — ribs, waist tuck, abdominal
fat — and the engine's plan accuracy drops fast without it. Re-engages
the Path's BCS node without making it feel like nagging.

Cooldown: one email per (uid, dog_id) per 28 days.

State cache: cache/body_check_reminder_state.json
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
    get_access_token, load_all_users, is_paid,
)
from pupshape_template_translator import get_localized
from pupshape_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'body_check_reminder'
DEEP_LINK = 'pupshape://body-check'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'body_check_reminder_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

_LOOKBACK_DAYS = 28


EN_SOURCE = {
    'subject': "Quick body check on {{dog_name}}?",
    'body': [
        "{{first_name}}, the scale only tells half the story for {{dog_name}}.",
        "It's been about a month since the last body-check. The 30-second one in-app — ribs feel, waist tuck from above, side-profile — is what tells the engine whether the weight number is the right weight number. Two dogs at 12 kg can be very differently fit.",
        "Today is a good day to do it. The plan will recalibrate the next time you weigh in, using the new score.",
        "P.S. The little BCS card lives under Today → Tasks. Sixty seconds, one tap each.",
    ],
    'cta': "Score {{dog_name}}'s body now",
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
    return {'dogs': {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _within_cooldown(prev_iso: str, days: int) -> bool:
    if not prev_iso:
        return False
    try:
        prev = datetime.fromisoformat(prev_iso)
    except Exception:
        return False
    return (datetime.now() - prev).days < days


def _last_bcs_ts(dog: dict):
    """Returns the timestamp of the most recent body_condition_score
    task completion for this dog, or None. Reads from a denormalised
    last_bcs_at on the dog, falling back to task_completions."""
    last = dog.get('last_body_check_at') or dog.get('last_bcs_at')
    if last:
        try:
            return datetime.fromisoformat(str(last).replace('Z', '+00:00').replace(' ', 'T'))
        except Exception:
            pass
    completions = dog.get('task_completions') or {}
    bcs = []
    for k, v in (completions.items() if isinstance(completions, dict) else []):
        if 'body_condition_score' not in str(k).lower():
            continue
        if isinstance(v, dict):
            ts = v.get('completed_at') or v.get('timestamp')
        else:
            ts = v
        if not ts:
            continue
        try:
            bcs.append(datetime.fromisoformat(str(ts).replace('Z', '+00:00').replace(' ', 'T')))
        except Exception:
            continue
    return max(bcs) if bcs else None


def main(dry_run: bool = False) -> None:
    print(f"\n🩺 Running {KIND}_sender (dry_run={dry_run})…")
    token = get_access_token()
    if not token:
        print("   ⚠️ no token — skipping")
        return

    users = list(load_all_users(token))
    state = _load_state()
    cutoff = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)

    candidates = []
    for user in users:
        uid = user.get('uid')
        email = user.get('email')
        if not uid or not email:
            continue
        for dog in user.get('dogs', []):
            dog_id = dog.get('dog_id')
            if not dog_id:
                continue
            last = _last_bcs_ts(dog)
            if last is not None:
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if last >= cutoff:
                    continue
            key = f"{uid}::{dog_id}"
            prev = (state.get('dogs', {}).get(key) or {}).get('sent_at')
            if _within_cooldown(prev, _LOOKBACK_DAYS):
                continue
            candidates.append((user, dog))
            break  # one nudge per user per run

    if not candidates:
        print('   ✅ No body-check candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} body-check nudges")
        for u, d in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  {u.get('language','en')}")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name': user.get('first_name', ''),
            'dog_name':   dog.get('name', 'your pup'),
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
            state.setdefault('dogs', {})[f"{user['uid']}::{dog['dog_id']}"] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  ({dog["name"]})  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
