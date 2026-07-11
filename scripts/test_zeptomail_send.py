#!/usr/bin/env python3
"""Quick ZeptoMail test send — thesisgenerator.io only."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gmail_sender import GmailSender


def main():
    to = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TEST_EMAIL")
    if not to:
        print("Usage: TEST_EMAIL=you@example.com python scripts/test_zeptomail_send.py")
        sys.exit(1)

    os.environ.setdefault("EMAIL_PROVIDER", "zeptomail")
    sender = GmailSender()
    if not sender.connect():
        sys.exit(1)

    html = """
    <p>ZeptoMail test from thesisgenerator.io — review-safe welcome path check.</p>
    """
    result = sender.send_email(
        to_email=to,
        subject="Thesis Generator — ZeptoMail test",
        html_body=html,
        from_name="Thesis Generator",
        tags=[{"name": "app", "value": "thesis_generator"}, {"name": "kind", "value": "test"}],
        ref_id="zeptomail-test",
    )
    print(f"Result: {result}")
    sys.exit(0 if result == "sent" else 1)


if __name__ == "__main__":
    main()
