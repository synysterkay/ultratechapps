/**
 * Resend send wrapper for Selka. Owns:
 *   - sender pool rotation (spreads reputation across the 7 Flow domains)
 *   - per-template HTML rendering (mobile-first, RTL-aware, brand palette)
 *   - the actual Resend API call
 *
 * Why a single render path instead of per-template HTML: every Selka email
 * is the same shape — preheader, body paragraphs, primary CTA, P.S., footer.
 * Centralizing means a brand tweak hits all 20+ templates at once.
 */

const {sendEmail, resolveSender} = require("../email_transport");
const {isRtl} = require("./translator");
const {APP_STORE_URL, PLAY_STORE_URL} = require("./templates");

const SENDER_POOL = [
  {email: "selka@kaynel.solutions", name: "Selka"},
  {email: "selka@passedai.io", name: "Selka"},
];

function pickSender() {
  return resolveSender(SENDER_POOL[Math.floor(Math.random() * SENDER_POOL.length)]);
}

/**
 * Render + send a Selka email.
 *
 * @param {Object} args
 * @param {Object} args.template       localized template (subject/body/cta/ps already in user's lang)
 * @param {Object} args.vars            personalization values for {placeholders}
 * @param {string} args.toEmail
 * @param {string} args.locale          for HTML dir + lang attributes
 * @param {string} args.resendApiKey
 * @returns {Promise<Object>}            Resend response (or throws)
 */
async function sendSelkaEmail({template, vars, toEmail, locale, resendApiKey}) {
  const sender = pickSender();
  const interp = (s) => interpolate(s, vars);

  const subject = interp(template.subject);
  const html = buildHtml({
    preheader: interp(template.preheader || ""),
    paragraphs: (template.body || []).map(interp),
    ctaLabel: interp(template.cta || "Open Selka"),
    ps: template.ps ? interp(template.ps) : null,
    locale,
  });

  const res = await sendEmail({
    apiKey: resendApiKey,
    fromEmail: sender.email,
    fromName: sender.name,
    toEmail,
    subject,
    html,
  });
  return res;
}

function interpolate(text, vars) {
  if (!text) return "";
  return String(text).replace(/\{(\w+)\}/g, (_, key) => {
    const val = vars[key];
    if (val === undefined || val === null || val === "") {
      // Sensible fallback per key — never show a raw {placeholder} to a user.
      return DEFAULTS[key] ?? "";
    }
    return String(val);
  });
}

const DEFAULTS = {
  name: "there",
  partner_name: "them",
  partner_a: "the first person",
  partner_b: "the second person",
  last_partner_risk: "concerning",
  top_pattern: "communication patterns",
  shared_pattern: "communication patterns",
  scan_count_total: "a few",
  scan_count: "a few",
  partner_count: "a few",
  streak_days: "0",
  credits_remaining: "1",
  referral_code: "(get yours in Settings)",
  referrals_count: "0",
  level: "1",
  new_level: "2",
  old_level: "1",
  pattern_name: "a new behavioral pattern",
  feature_name: "comparison mode",
  feature_one_liner: "scan two people and I'll show you what they share",
  retro_insight_hint: "the pattern around honesty signals",
};

function buildHtml({preheader, paragraphs, ctaLabel, ps, locale}) {
  const rtl = isRtl(locale);
  const dirAttr = rtl ? ' dir="rtl"' : "";
  const align = rtl ? "right" : "left";
  const langAttr = ` lang="${locale}"`;

  const bodyHtml = paragraphs
      .map((p) => `<p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:#1f2937;text-align:${align};">${renderInline(p)}</p>`)
      .join("\n");

  const psHtml = ps ?
    `<div style="margin:28px 0 0;padding:14px 16px;background:#f3f0ff;border-radius:10px;border:1px solid #ddd6fe;">
       <p style="margin:0;font-size:14px;line-height:1.6;color:#4c1d95;text-align:${align};">P.S. ${renderInline(ps)}</p>
     </div>` : "";

  // Selka brand palette — lavender primary, teal accent.
  const cta = `
    <div style="text-align:center;margin:32px 0 24px;">
      <a href="${APP_STORE_URL}" style="display:inline-block;background:#8b5cf6;color:#ffffff;padding:14px 28px;border-radius:12px;font-weight:600;font-size:16px;text-decoration:none;margin:4px;">
        ${ctaLabel}
      </a>
    </div>
    <p style="text-align:center;font-size:13px;color:#6b7280;margin:0 0 24px;">
      <a href="${APP_STORE_URL}" style="color:#6b7280;text-decoration:underline;">iOS</a> &nbsp;·&nbsp;
      <a href="${PLAY_STORE_URL}" style="color:#6b7280;text-decoration:underline;">Android</a>
    </p>`;

  return `<!doctype html>
<html${dirAttr}${langAttr}>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta name="color-scheme" content="light only">
  <meta name="supported-color-schemes" content="light only">
</head>
<body style="margin:0;padding:0;background:#faf9fc;font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',Roboto,sans-serif;">
  <span style="display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;font-size:1px;line-height:1px;">${escapeHtml(preheader)}</span>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#faf9fc;">
    <tr><td align="center" style="padding:40px 16px;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#ffffff;border-radius:18px;box-shadow:0 1px 3px rgba(15,12,30,0.04);overflow:hidden;">
        <tr><td style="padding:36px 36px 0;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px;">
            <div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#a78bfa,#7c3aed);display:inline-block;vertical-align:middle;"></div>
            <span style="font-family:Georgia,serif;font-size:20px;color:#1f2937;font-weight:600;vertical-align:middle;margin-${rtl ? "right" : "left"}:10px;">Selka</span>
          </div>
          ${bodyHtml}
          ${cta}
          ${psHtml}
        </td></tr>
        <tr><td style="padding:28px 36px 36px;border-top:1px solid #f3f4f6;">
          <p style="margin:0 0 6px;font-size:12px;color:#9ca3af;text-align:center;">Selka · Decode chats. Date with clarity.</p>
          <p style="margin:0;font-size:11px;color:#d1d5db;text-align:center;">San Francisco, CA · You're receiving this because you signed up for Selka. <a href="${APP_STORE_URL}" style="color:#9ca3af;text-decoration:underline;">Manage in app</a></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

// Light markdown: **bold** + *italic* only. Keeps the template content
// readable in source while still rendering rich in the email client.
function renderInline(text) {
  return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function escapeHtml(s) {
  return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
}

module.exports = {sendSelkaEmail, pickSender};
