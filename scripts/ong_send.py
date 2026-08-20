#!/usr/bin/env python3
"""Shared send + daily cap for ONG retention emails."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from gmail_sender import GmailSender, has_email_credentials
from ong_email_chrome import render as render_email

APP_NAME = 'ONG'
APP_SLUG = 'ong'
DEEP_LINK = 'https://sealed-cce0a.web.app'
DAILY_CAP = int(os.getenv('ONG_DAILY_SEND_CAP', '30'))
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
QUOTA_FILE = Path(__file__).parent.parent / 'cache' / 'ong_daily_quota.json'


def ref_id(email: str) -> str:
    return hashlib.sha256(f'{_REF_SALT}::{email.lower()}'.encode()).hexdigest()[:16]


def _today() -> str:
    n = datetime.now(timezone.utc)
    return f'{n.year}-{n.month:02d}-{n.day:02d}'


def _quota():
    if QUOTA_FILE.exists():
        try:
            return json.loads(QUOTA_FILE.read_text())
        except Exception:
            pass
    return {'days': {}}


def remaining() -> int:
    data = _quota()
    used = int((data.get('days') or {}).get(_today(), 0))
    return max(0, DAILY_CAP - used)


def consume() -> bool:
    if remaining() <= 0:
        return False
    data = _quota()
    days = data.setdefault('days', {})
    today = _today()
    days[today] = int(days.get(today, 0)) + 1
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(data, indent=2))
    return True


def connect_sender():
    if not has_email_credentials():
        print('❌ Email credentials not set')
        return None
    sender = GmailSender()
    if not sender.connect():
        return None
    return sender


def send_ong(sender, *, email, subject, paragraphs, cta, kind, lang='en',
             stage=None, gradient='invite', from_name=None, signoff_override=None):
    if remaining() <= 0:
        print('   ⏭️ ONG daily cap reached')
        return 'throttled'
    sender_name = from_name or APP_NAME
    html = render_email(
        lang, paragraphs, cta, DEEP_LINK,
        sender_name=sender_name, app_name=APP_NAME, gradient=gradient,
        signoff_override=signoff_override,
    )
    tags = [
        {'name': 'app', 'value': APP_SLUG},
        {'name': 'kind', 'value': kind},
        {'name': 'language', 'value': lang},
    ]
    if stage:
        tags.append({'name': 'stage', 'value': str(stage)})
    result = sender.send_email(
        to_email=email,
        subject=subject,
        html_body=html,
        from_name=sender_name,
        tags=tags,
        ref_id=ref_id(email),
    )
    if result == 'sent':
        consume()
    return result


def load_state(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {'users': {}}


def save_state(path: Path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
