#!/usr/bin/env bash
# Configure ZeptoMail Agent 2 (breakuprelief.com) hard-bounce webhook.
# Same Supabase endpoint + auth key as Agent 1 — add separately per Agent in ZeptoMail.
#
# Usage:
#   ./scripts/setup_zeptomail_agent2_webhook.sh          # verify endpoint + print dashboard steps
#   ./scripts/setup_zeptomail_agent2_webhook.sh --test   # send a signed test hard-bounce payload

set -euo pipefail

WEBHOOK_URL="https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/zeptomail-webhook"
AUTH_KEY_FILE="$(cd "$(dirname "$0")/.." && pwd)/.zeptomail_webhook_auth_key"

if [[ -f "$AUTH_KEY_FILE" ]]; then
  AUTH_KEY="$(tr -d '[:space:]' < "$AUTH_KEY_FILE")"
else
  AUTH_KEY="${ZEPTOMAIL_WEBHOOK_AUTH_KEY:-}"
fi

echo "════════════════════════════════════════════════════════════"
echo " ZeptoMail Agent 2 webhook — breakuprelief.com"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Endpoint (same as Agent 1):"
echo "  $WEBHOOK_URL"
echo ""

echo "1) Checking endpoint is live..."
HTTP=$(curl -sS -o /tmp/zm-wh-health.json -w "%{http_code}" "$WEBHOOK_URL" || true)
if [[ "$HTTP" == "200" ]]; then
  echo "   ✅ GET $HTTP — $(cat /tmp/zm-wh-health.json)"
else
  echo "   ⚠️  GET returned $HTTP (expected 200). Deploy first:"
  echo "      supabase functions deploy zeptomail-webhook --project-ref jimcdgkwbbrxgakingtg"
fi
echo ""

if [[ -z "$AUTH_KEY" ]]; then
  echo "2) Auth key: not found locally."
  echo "   Set ZEPTOMAIL_WEBHOOK_AUTH_KEY or create .zeptomail_webhook_auth_key"
  echo "   (must match Supabase secret ZEPTOMAIL_WEBHOOK_AUTH_KEY)"
else
  echo "2) Auth key: loaded (${#AUTH_KEY} chars)"
fi
echo ""

echo "3) ZeptoMail dashboard — Agent 2 (breakuprelief.com):"
echo "   a. Mail Agents → select Agent 2 (breakuprelief.com)"
echo "   b. Webhooks tab → Authentication Key (top right)"
echo "      Paste the SAME key as Agent 1 / Supabase ZEPTOMAIL_WEBHOOK_AUTH_KEY"
echo "   c. Add Webhook:"
echo "      URL:         $WEBHOOK_URL"
echo "      Description: Supabase hard-bounce suppressions (Fresh Start + Selka + SoulPlan)"
echo "      Events:      ☑ Hard bounced only"
echo "   d. Send Test → Hard bounce → should return 200"
echo ""
echo "   Bounces write to email_suppressions + email_events."
echo "   Skipped automatically by check-new-users + welcome-email."
echo ""

if [[ "${1:-}" == "--test" ]]; then
  if [[ -z "$AUTH_KEY" ]]; then
    echo "❌ Cannot --test without auth key"
    exit 1
  fi
  echo "4) Sending test hard-bounce (hello@breakuprelief.com / fresh_start)..."
  RESP=$(curl -sS -w "\nHTTP:%{http_code}" -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -H "x-zeptomail-auth: $AUTH_KEY" \
    -d '{
      "event_name": ["hardbounce"],
      "event_message": [{
        "email_info": {
          "from": {"address": "hello@breakuprelief.com", "name": "Fresh Start"},
          "to": [{"email_address": {"address": "webhook-test-suppressed@example.invalid"}}],
          "mime_headers": {"X-Tag-app": "fresh_start", "X-Tag-kind": "welcome"}
        }
      }]
    }')
  echo "$RESP"
  echo ""
  echo "   If HTTP:200 and ok:true, webhook + auth are working."
fi

echo "════════════════════════════════════════════════════════════"
