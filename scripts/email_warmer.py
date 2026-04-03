#!/usr/bin/env python3
"""
Email Warming System
Warms sender domains by exchanging emails with Gmail seed accounts.

Two tiers:
  - Full warming (Cloudflare domains): Send via Resend → Gmail opens via IMAP → Gmail replies
  - Open-only (other domains): Send via Resend → Gmail opens via IMAP (no replies)

Usage:
  python3 scripts/email_warmer.py              # Run warming cycle
  python3 scripts/email_warmer.py --dry-run    # Preview what would be sent
"""
import os
import sys
import json
import time
import random
import imaplib
import email as email_lib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
import requests

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.warming_templates import get_warming_email, get_reply_body

# ─── CONFIG ──────────────────────────────────────────────

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_API_URL = "https://api.resend.com/emails"

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "warming_config.json")
STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "warming_state.json")
HEALTH_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "sender_health.json")

# Gmail App Passwords (from env)
# Format: GMAIL_APP_PWD_anaskay_13=xxxx
def _get_gmail_password(gmail_address):
    """Get app password for a Gmail account from environment."""
    # Convert email to env var name: anaskay.13@gmail.com -> GMAIL_APP_PWD_ANASKAY_13
    local = gmail_address.split("@")[0]
    key = "GMAIL_APP_PWD_" + local.upper().replace(".", "_")
    pwd = os.getenv(key, "")
    if not pwd:
        print(f"   ⚠️  No app password found for {gmail_address} (env: {key})")
    return pwd


# ─── STATE MANAGEMENT ───────────────────────────────────

def _load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default or {}


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _load_config():
    return _load_json(CONFIG_PATH)


def _load_state():
    return _load_json(STATE_PATH, {
        "warming_started": datetime.now(timezone.utc).isoformat(),
        "total_sent": 0,
        "total_opened": 0,
        "total_replied": 0,
        "daily_log": {},
        "per_domain": {},
    })


def _save_state(state):
    _save_json(STATE_PATH, state)


def _get_current_week(state):
    """Calculate which warming week we're in (1-indexed)."""
    started = datetime.fromisoformat(state.get("warming_started", datetime.now(timezone.utc).isoformat()))
    days = (datetime.now(timezone.utc) - started.replace(tzinfo=timezone.utc if started.tzinfo is None else started.tzinfo)).days
    return max(1, (days // 7) + 1)


def _get_ramp_target(config, week):
    """Get per-sender warming target for current week."""
    schedule = config.get("ramp_schedule", {})
    if week == 1:
        return schedule.get("week_1", {}).get("warm_per_sender", 5)
    elif week == 2:
        return schedule.get("week_2", {}).get("warm_per_sender", 10)
    elif week == 3:
        return schedule.get("week_3", {}).get("warm_per_sender", 15)
    else:
        return schedule.get("week_4_plus", {}).get("warm_per_sender", 20)


def _get_domain_health(domain):
    """Read domain health from sender_health.json."""
    health_data = _load_json(HEALTH_PATH)
    senders = health_data.get("senders", {})
    for sender_email, info in senders.items():
        if domain in sender_email:
            return info.get("status", "unknown")
    return "unknown"


# ─── SEND VIA RESEND ────────────────────────────────────

def send_warming_email(from_email, from_name, to_email, subject, body, dry_run=False):
    """Send a warming email via Resend API."""
    if dry_run:
        print(f"   [DRY RUN] Would send: {from_email} → {to_email}: '{subject}'")
        return True

    if not RESEND_API_KEY:
        print("   ❌ RESEND_API_KEY not set")
        return False

    html_body = f"""<div style="font-family: -apple-system, Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
<p>{body}</p>
<p style="margin-top: 20px; color: #666;">Best,<br>{from_name}</p>
</div>"""

    try:
        resp = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{from_name} <{from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "reply_to": from_email,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            print(f"   ✅ Sent: {from_email} → {to_email}: '{subject}'")
            return True
        else:
            print(f"   ❌ Resend error [{resp.status_code}]: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Send error: {e}")
        return False


# ─── GMAIL IMAP OPERATIONS ──────────────────────────────

def open_emails_via_imap(gmail_address, app_password, from_domain, dry_run=False):
    """
    Connect to Gmail via IMAP and mark warming emails as read (= 'opened').
    Returns list of (subject, from_addr, message_id) for potential replies.
    """
    if dry_run:
        print(f"   [DRY RUN] Would open emails in {gmail_address} from *@{from_domain}")
        return []

    if not app_password:
        print(f"   ⚠️  Skipping IMAP for {gmail_address} — no app password")
        return []

    opened = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail_address, app_password)
        mail.select("INBOX")

        # Search for unread emails from the warming domain
        status, messages = mail.search(None, f'(UNSEEN FROM "@{from_domain}")')
        if status != "OK" or not messages[0]:
            mail.logout()
            return []

        msg_ids = messages[0].split()
        for msg_id in msg_ids[:10]:  # Cap at 10 per check
            # Fetch the email (this marks it as SEEN = opened)
            status, data = mail.fetch(msg_id, "(RFC822)")
            if status == "OK":
                msg = email_lib.message_from_bytes(data[0][1])
                subject = msg.get("Subject", "")
                from_addr = msg.get("From", "")
                message_id = msg.get("Message-ID", "")
                opened.append((subject, from_addr, message_id))
                print(f"   👁️  Opened: '{subject}' from {from_addr}")

            # Small delay between opens to look natural
            time.sleep(random.uniform(2, 8))

        # Also check spam and rescue if found
        mail.select("[Gmail]/Spam")
        status, spam_msgs = mail.search(None, f'(FROM "@{from_domain}")')
        if status == "OK" and spam_msgs[0]:
            spam_ids = spam_msgs[0].split()
            for msg_id in spam_ids[:5]:
                # Move from spam to inbox (mark as not spam)
                mail.store(msg_id, "+FLAGS", "\\Seen")
                mail.copy(msg_id, "INBOX")
                mail.store(msg_id, "+FLAGS", "\\Deleted")
                print(f"   🛟 Rescued email from spam in {gmail_address}")
            mail.expunge()

        mail.logout()
    except Exception as e:
        print(f"   ❌ IMAP error for {gmail_address}: {e}")

    return opened


def reply_via_gmail(gmail_address, app_password, to_email, subject, reply_body,
                    original_message_id=None, dry_run=False):
    """Send a reply from Gmail via SMTP to create a conversation."""
    if dry_run:
        print(f"   [DRY RUN] Would reply: {gmail_address} → {to_email}: Re: {subject}")
        return True

    if not app_password:
        print(f"   ⚠️  Skipping reply from {gmail_address} — no app password")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = gmail_address
        msg["To"] = to_email
        msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
        if original_message_id:
            msg["In-Reply-To"] = original_message_id
            msg["References"] = original_message_id

        msg.attach(MIMEText(reply_body, "plain"))

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, to_email, msg.as_string())
        server.quit()

        print(f"   💬 Replied: {gmail_address} → {to_email}: Re: {subject}")
        return True
    except Exception as e:
        print(f"   ❌ SMTP reply error: {e}")
        return False


# ─── MAIN WARMING LOGIC ─────────────────────────────────

def run_warming_cycle(dry_run=False):
    """Execute one warming cycle across all domains."""
    config = _load_config()
    state = _load_state()
    week = _get_current_week(state)
    target_per_sender = _get_ramp_target(config, week)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"🔥 EMAIL WARMING — Week {week}, Target: {target_per_sender}/sender")
    print(f"   Date: {today}, Dry run: {dry_run}")
    print(f"{'='*60}\n")

    reply_config = config.get("reply_behavior", {})
    timing = config.get("timing", {})

    stats = {"sent": 0, "opened": 0, "replied": 0, "spam_rescued": 0}

    # ── 1. Full warming domains (Cloudflare — can receive replies) ──
    print("── FULL WARMING (Cloudflare domains) ──")
    for domain, info in config.get("full_warming_domains", {}).items():
        print(f"\n📧 Domain: {domain}")
        health = _get_domain_health(domain)
        print(f"   Health: {health}")

        warmer_addresses = info.get("warmer_addresses", [])
        forwarding = info.get("forwarding", {})

        sends_today = state.get("per_domain", {}).get(domain, {}).get(today, {}).get("sent", 0)
        remaining = max(0, target_per_sender - sends_today)

        if remaining == 0:
            print(f"   ✓ Already hit target for today ({target_per_sender})")
            continue

        for i in range(remaining):
            # Pick a warmer address and its forwarding Gmail
            warmer = random.choice(warmer_addresses)
            gmail_dest = forwarding.get(warmer)
            if not gmail_dest:
                continue

            # Send warming email via Resend
            subject, body = get_warming_email()
            from_name = random.choice(["Alex", "Jordan", "Casey", "Sam"])
            success = send_warming_email(warmer, from_name, gmail_dest, subject, body, dry_run)

            if success:
                stats["sent"] += 1

            # Random delay between sends
            delay = random.uniform(
                timing.get("delay_between_sends_min_sec", 600),
                timing.get("delay_between_sends_max_sec", 2700),
            )
            if not dry_run:
                # In CI, use shorter delays (full delays handled by staggered cron)
                actual_delay = min(delay, 30)
                time.sleep(actual_delay)

        # Open emails via IMAP for each Gmail that receives from this domain
        print(f"\n   Opening emails in Gmail for {domain}...")
        for warmer_addr, gmail_addr in forwarding.items():
            app_pwd = _get_gmail_password(gmail_addr)
            opened = open_emails_via_imap(gmail_addr, app_pwd, domain, dry_run)
            stats["opened"] += len(opened)

            # Decide on reply behavior
            for subject, from_addr, message_id in opened:
                roll = random.randint(1, 100)
                reply_threshold = reply_config.get("open_and_reply_pct", 40) + reply_config.get("open_reply_thread_pct", 20)

                if roll <= reply_threshold:
                    # Wait before replying (looks natural)
                    if not dry_run:
                        time.sleep(random.uniform(5, 30))

                    reply_body = get_reply_body(subject)
                    # Extract the actual sender address for reply
                    reply_to = warmer_addr  # Reply back to the warmer address
                    replied = reply_via_gmail(gmail_addr, app_pwd, reply_to, subject,
                                             reply_body, message_id, dry_run)
                    if replied:
                        stats["replied"] += 1

    # ── 2. Open-only domains (no Cloudflare — can't receive) ──
    print("\n── OPEN-ONLY WARMING (non-Cloudflare domains) ──")
    for domain, info in config.get("open_only_domains", {}).items():
        print(f"\n📧 Domain: {domain}")
        health = _get_domain_health(domain)
        print(f"   Health: {health}")

        sender_addresses = info.get("sender_addresses", [])
        seed_gmail = info.get("seed_gmail", "")

        if not seed_gmail:
            print(f"   ⚠️  No seed Gmail configured for {domain}")
            continue

        sends_today = state.get("per_domain", {}).get(domain, {}).get(today, {}).get("sent", 0)
        remaining = max(0, target_per_sender - sends_today)

        if remaining == 0:
            print(f"   ✓ Already hit target for today ({target_per_sender})")
            continue

        # For open-only domains, we only need the 3 Gmail accounts that have app passwords
        # to open the emails. We send TO the seed Gmail, then open via one of
        # the authenticated Gmails if the seed is one of them.
        for i in range(remaining):
            sender = random.choice(sender_addresses)
            subject, body = get_warming_email()
            from_name = random.choice(["Alex", "Jordan", "Casey", "Sam", "Morgan", "Taylor"])
            success = send_warming_email(sender, from_name, seed_gmail, subject, body, dry_run)

            if success:
                stats["sent"] += 1

            if not dry_run:
                time.sleep(random.uniform(10, 30))

        # Try to open emails if we have app password for this seed Gmail
        app_pwd = _get_gmail_password(seed_gmail)
        if app_pwd:
            print(f"   Opening emails in {seed_gmail} from {domain}...")
            opened = open_emails_via_imap(seed_gmail, app_pwd, domain, dry_run)
            stats["opened"] += len(opened)
        else:
            print(f"   ℹ️  No app password for {seed_gmail} — emails sent but can't auto-open")

    # ── 3. Update state ──
    state["total_sent"] = state.get("total_sent", 0) + stats["sent"]
    state["total_opened"] = state.get("total_opened", 0) + stats["opened"]
    state["total_replied"] = state.get("total_replied", 0) + stats["replied"]

    if today not in state.get("daily_log", {}):
        state.setdefault("daily_log", {})[today] = {}
    state["daily_log"][today] = {
        "sent": state["daily_log"].get(today, {}).get("sent", 0) + stats["sent"],
        "opened": state["daily_log"].get(today, {}).get("opened", 0) + stats["opened"],
        "replied": state["daily_log"].get(today, {}).get("replied", 0) + stats["replied"],
        "week": week,
    }

    _save_state(state)

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"📊 WARMING SUMMARY")
    print(f"   Sent: {stats['sent']}")
    print(f"   Opened: {stats['opened']}")
    print(f"   Replied: {stats['replied']}")
    print(f"   Spam rescued: {stats['spam_rescued']}")
    print(f"   Lifetime: {state['total_sent']} sent, {state['total_opened']} opened, {state['total_replied']} replied")
    print(f"{'='*60}\n")

    return stats


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_warming_cycle(dry_run=dry_run)
