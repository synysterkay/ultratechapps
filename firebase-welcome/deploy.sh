#!/usr/bin/env bash
set -euo pipefail

# Deploy the welcome email Cloud Function to all 6 Firebase projects.
# Usage:
#   ./deploy.sh                        # deploy to all projects
#   ./deploy.sh predictify-3f30d       # deploy to a single project
#
# Prerequisites:
#   - firebase-tools installed: npm install -g firebase-tools
#   - Logged in: firebase login  (or use FIREBASE_TOKEN env var)
#   - RESEND_API_KEY, MAILGUN_API_KEY, or SMTP2GO_API_KEY set per project / .env

PROJECTS=(
  "predictify-3f30d"
  "thesis-generator-web"
  "redflagscanner"
  "breakuptherapy-e7dc0"
  "soulplan-dateplanner"
  "petmealai"
  # NOTE: boyfriend-ai-f1e5e and apb412---ai-girlfriend-app intentionally
  # NOT included here. They are on Firebase Spark (free) plan, which can't
  # use Cloud Functions secrets. Welcome emails for both apps are delivered
  # via the Supabase check-new-users Edge Function (~5 min after signup
  # instead of instant) — see supabase/functions/check-new-users/index.ts.
  # Re-add them here only if those projects are upgraded to Blaze.
)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Install deps if needed
if [ ! -d "functions/node_modules" ]; then
  echo "📦 Installing Cloud Function dependencies..."
  cd functions && npm install && cd ..
fi

# If a single project is specified, deploy only to that one
if [ $# -ge 1 ]; then
  PROJECTS=("$1")
fi

FAILED=()

for PROJECT_ID in "${PROJECTS[@]}"; do
  echo ""
  echo "🚀 Deploying to ${PROJECT_ID}..."

  # Need Resend, Mailgun, or SMTP2GO credentials (secret or functions/.env).
  has_resend=0
  has_mailgun=0
  has_smtp2go=0
  firebase functions:secrets:access RESEND_API_KEY --project "$PROJECT_ID" > /dev/null 2>&1 && has_resend=1
  firebase functions:secrets:access MAILGUN_API_KEY --project "$PROJECT_ID" > /dev/null 2>&1 && has_mailgun=1
  firebase functions:secrets:access SMTP2GO_API_KEY --project "$PROJECT_ID" > /dev/null 2>&1 && has_smtp2go=1
  if [ -f "functions/.env" ] && grep -q '^SMTP2GO_API_KEY=' functions/.env 2>/dev/null; then
    has_smtp2go=1
  fi
  if [ "$has_resend" -eq 0 ] && [ "$has_mailgun" -eq 0 ] && [ "$has_smtp2go" -eq 0 ]; then
    echo "⚠️  No email API key for $PROJECT_ID (RESEND, MAILGUN, or SMTP2GO)."
    echo "   Set functions/.env or: firebase functions:secrets:set SMTP2GO_API_KEY --project $PROJECT_ID"
    FAILED+=("$PROJECT_ID (missing secret)")
    continue
  fi

  # CRITICAL: list each welcome-pipeline function with --only.
  # The redflagscanner Firebase project also hosts the Red Flag Scanner
  # app's own ~17 functions under the same `default` codebase. An
  # un-scoped `firebase deploy --only functions` from this directory
  # would delete every app function that isn't declared in our
  # functions/index.js — wiping auth, scans, credits, notifications,
  # referrals, the lifecycle emitters, etc. Always list explicitly.
  WELCOME_FUNCS="functions:sendWelcomeEmail"
  if [ "$PROJECT_ID" = "redflagscanner" ]; then
    WELCOME_FUNCS="$WELCOME_FUNCS,functions:sendSelkaWelcome,functions:onSelkaEmailEvent"
  fi

  if firebase deploy --only "$WELCOME_FUNCS" --project "$PROJECT_ID" --force; then
    echo "✅ ${PROJECT_ID} deployed successfully"
  else
    echo "❌ ${PROJECT_ID} deployment failed"
    FAILED+=("$PROJECT_ID")
  fi
done

echo ""
echo "════════════════════════════════════════"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "✅ All projects deployed successfully!"
else
  echo "⚠️  Failed deployments:"
  for f in "${FAILED[@]}"; do
    echo "   - $f"
  done
fi
echo "════════════════════════════════════════"
