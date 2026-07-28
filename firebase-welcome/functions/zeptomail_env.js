/**
 * ZeptoMail helpers for Firebase Cloud Functions.
 * API keys live in functions/.env (gitignored) or Firebase Secret Manager.
 *   ZEPTOMAIL_BREAKUP_API_KEY — Agent 2 token (breakuprelief.com)
 *   ZEPTOMAIL_API_KEY         — fallback (Agent 1)
 */
function isZeptomailProvider() {
  return (process.env.EMAIL_PROVIDER || "").toLowerCase() === "zeptomail";
}

module.exports = {isZeptomailProvider};
