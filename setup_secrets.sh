#!/bin/bash

# Load environment variables from .env
source .env

echo "Setting up GitHub Secrets from .env file..."

# Set GitHub repository secrets
gh secret set DEEPSEEK_API_KEY --body "$DEEPSEEK_API_KEY" --repo synysterkay/marketingtool
echo "✅ DEEPSEEK_API_KEY set"

gh secret set DEVTO_API_KEY --body "$DEVTO_API_KEY" --repo synysterkay/marketingtool
echo "✅ DEVTO_API_KEY set"

gh secret set HASHNODE_API_KEY --body "$HASHNODE_API_KEY" --repo synysterkay/marketingtool
echo "✅ HASHNODE_API_KEY set"

gh secret set HASHNODE_PUBLICATION_ID --body "$HASHNODE_PUBLICATION_ID" --repo synysterkay/marketingtool
echo "✅ HASHNODE_PUBLICATION_ID set"

gh secret set BLUESKY_HANDLE --body "$BLUESKY_HANDLE" --repo synysterkay/marketingtool
echo "✅ BLUESKY_HANDLE set"

gh secret set BLUESKY_PASSWORD --body "$BLUESKY_PASSWORD" --repo synysterkay/marketingtool
echo "✅ BLUESKY_PASSWORD set"

echo ""
echo "🎉 All secrets configured successfully!"
echo ""
echo "View your secrets at:"
echo "https://github.com/synysterkay/marketingtool/settings/secrets/actions"
