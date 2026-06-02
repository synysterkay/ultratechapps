#!/usr/bin/env python3
"""
Streak-Milestone Sender (PupShape)

Fires when a user's usage.streak.current first hits 3 / 7 / 14 / 30 /
100 days — the externalised celebration arm of the Hooked loop. Each
threshold gets exactly one email per user (dedupe per (uid, threshold)).

Renamed to `pupshape_streak_milestone_sender` so the import doesn't
collide with the Thesis streak_milestone_sender — both apps run in the
same retention-emails.yml workflow.

State cache: cache/pupshape_streak_milestone_state.json
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime

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
KIND = 'streak_milestone'
DEEP_LINK = 'pupshape://streak'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'pupshape_streak_milestone_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Streak thresholds we celebrate, ascending.
STAGES = [3, 7, 14, 30, 100]


EN_SOURCES = {
    3: {
        'subject': "3-day streak with {{dog_name}} 🐾",
        'body': [
            "{{first_name}}, three days. That's the unglamorous milestone that quietly predicts the long ones.",
            "Most people who hit a 3-day streak don't even notice it. Most who hit a 30-day streak started by noticing it. So: noted, on the record, you and {{dog_name}} are now a streak.",
            "P.S. The streak counter lives on the home screen. Keep an eye on it — it's the cheapest accountability you'll ever get.",
        ],
        'cta': "See {{dog_name}}'s streak",
    },
    7: {
        'subject': "One week with {{dog_name}} — the data is talking now",
        'body': [
            "{{first_name}}, seven straight days. The plan now has enough signal to start being smart instead of just consistent.",
            "From here on, the engine learns from velocity, not just snapshots — small tweaks to {{dog_name}}'s plan based on what's actually happening, not what should be. That's the part most weight-loss apps never reach because most people don't make it to day 7.",
            "P.S. Same time tomorrow keeps the streak intact and the data clean. Same scale, same time, before breakfast.",
        ],
        'cta': "See what changed for {{dog_name}}",
    },
    14: {
        'subject': "Two weeks of {{dog_name}} — habit territory",
        'body': [
            "{{first_name}}, 14 days. By most definitions of habit research, this is the threshold where the daily check goes from \"thing I'm doing\" to \"thing I do.\"",
            "It's also the first window where the plan can show you a real trend line, not a noisy zig-zag. Open it today — the slope is the part to look at, not any single number.",
            "P.S. If you've been doing this without telling anyone, this is the milestone worth mentioning. Friends ask why you're up early — \"weighing the dog\" is a great answer.",
        ],
        'cta': "See {{dog_name}}'s trend",
    },
    30: {
        'subject': "30-day streak 🏆 — {{dog_name}}'s longest yet",
        'body': [
            "{{first_name}}, thirty unbroken days with {{dog_name}}.",
            "This is the streak almost nobody hits. The vet who said \"feed less, exercise more\" assumed you'd give up at week two — most people do. The trend in the app right now is the receipt that you didn't.",
            "P.S. There's a shareable 30-day card on the streak screen. The friend most likely to envy a streak is the one most likely to start their own — the math on whose dog ends up healthier writes itself.",
        ],
        'cta': "See {{dog_name}}'s 30-day card",
    },
    100: {
        'subject': "100 days with {{dog_name}} 🎉 — this is rare",
        'body': [
            "{{first_name}}, one hundred days. Less than a fraction of one percent of dog-weight apps get a user this far.",
            "There isn't a clever marketing way to put this — you and {{dog_name}} are now in a category where the app starts learning from *you* instead of the other way around. The plan model improves for every user from data points like yours.",
            "P.S. We will never email you about a 100-day streak twice. This is the once-ever message. Take a screenshot.",
        ],
        'cta': "See {{dog_name}}'s 100-day card",
    },
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
    return {'users': {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _current_streak(user: dict) -> int:
    usage = user.get('usage') or {}
    streak = usage.get('streak') or {}
    try:
        return int(streak.get('current') or 0)
    except (TypeError, ValueError):
        return 0


def _next_unfired_stage(current: int, fired: set) -> int:
    """Largest threshold ≤ current that hasn't fired for this user yet."""
    eligible = [s for s in STAGES if s <= current and s not in fired]
    return max(eligible) if eligible else 0


def main(dry_run: bool = False) -> None:
    print(f"\n🔥 Running pupshape_{KIND}_sender (dry_run={dry_run})…")
    token = get_access_token()
    if not token:
        print("   ⚠️ no token — skipping")
        return

    users = list(load_all_users(token))
    state = _load_state()

    candidates = []
    for user in users:
        uid = user.get('uid')
        email = user.get('email')
        if not uid or not email:
            continue
        current = _current_streak(user)
        if current < STAGES[0]:
            continue
        fired = set((state.get('users', {}).get(uid) or {}).get('stages', []))
        stage = _next_unfired_stage(current, fired)
        if not stage:
            continue
        dogs = user.get('dogs', [])
        lead_dog = dogs[0] if dogs else {'name': 'your pup', 'image_url': ''}
        candidates.append((user, lead_dog, stage))

    if not candidates:
        print('   ✅ No streak-milestone candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} streak milestones")
        for u, d, s in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  stage={s}")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, stage in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name':  user.get('first_name', ''),
            'dog_name':    dog.get('name', 'your pup'),
            'streak_days': str(stage),
        }
        en = EN_SOURCES[stage]
        # Templates are keyed `streak_milestone_stage_{N}` in the cache.
        tpl = get_localized(f"{KIND}_stage_{stage}", lang, en)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', en['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', en['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', en['cta']), ctx)
        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='celebrate', celebratory=True,
            dog_image_url=dog.get('image_url') or '',
            dog_name=dog.get('name', ''),
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'stage', 'value': str(stage)},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            rec['language'] = lang
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  stage={stage}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
