/**
 * Pluggable email transport for Firebase Cloud Functions.
 * EMAIL_PROVIDER: resend | mailgun | smtp2go | zeptomail
 *
 * ZeptoMail Agent 2 (breakuprelief.com): set ZEPTOMAIL_BREAKUP_API_KEY for
 * Fresh Start + Selka + SoulPlan Firebase sends. Agent 1 key stays on ZEPTOMAIL_API_KEY.
 */

const https = require("https");
const querystring = require("querystring");

const BREAKUP_APPS = new Set([
  "fresh_start",
  "breakup_therapy",
  "red_flag_scanner",
  "redflag",
  "soulplan",
]);
const SELKA_APPS = new Set(["red_flag_scanner", "redflag"]);

function emailProvider() {
  const p = (process.env.EMAIL_PROVIDER || "resend").toLowerCase();
  if (p === "mailgun") return "mailgun";
  if (p === "smtp2go") return "smtp2go";
  if (p === "zeptomail") return "zeptomail";
  return "resend";
}

function isBreakupApp(appTag) {
  return BREAKUP_APPS.has(String(appTag || "").toLowerCase());
}

function isSelkaApp(appTag) {
  return SELKA_APPS.has(String(appTag || "").toLowerCase());
}

function isOngApp(appTag) {
  const a = String(appTag || "").toLowerCase();
  return a === "ong" || a === "sealed";
}

const KAYNEL_CATCHALL_APPS = new Set([
  "pupshape",
  "kinbound",
  "volume_booster",
  "volume_booster_pro",
  "bass_booster",
  "loud_eq",
  "loudify",
  "ai_boyfriend",
  "ai_girlfriend",
  "smart_notes",
  "onbrief",
]);

function isKaynelApp(appTag) {
  const a = String(appTag || "").toLowerCase();
  return isOngApp(a) || KAYNEL_CATCHALL_APPS.has(a);
}

function zeptomailApiKey(appTag) {
  if (isBreakupApp(appTag) || isKaynelApp(appTag)) {
    return process.env.ZEPTOMAIL_BREAKUP_API_KEY || process.env.ZEPTOMAIL_API_KEY;
  }
  return process.env.ZEPTOMAIL_API_KEY;
}

function isEmailSendingPaused() {
  const v = (process.env.EMAIL_SENDING_PAUSED || "").toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

function hasEmailCredentials(apiKey, appTag) {
  const provider = emailProvider();
  if (provider === "mailgun") {
    return !!(process.env.MAILGUN_API_KEY && process.env.MAILGUN_DOMAIN);
  }
  if (provider === "smtp2go") {
    return !!process.env.SMTP2GO_API_KEY;
  }
  if (provider === "zeptomail") {
    return !!zeptomailApiKey(appTag);
  }
  return !!apiKey;
}

function resolveSender(poolSender, appTag) {
  const provider = emailProvider();
  if (provider === "mailgun") {
    const isSelka = String(poolSender.email || "").toLowerCase().startsWith("selka@");
    return {
      email: isSelka
        ? (process.env.MAILGUN_SELKA_SENDER_EMAIL || "selka@passedai.io")
        : (process.env.MAILGUN_SENDER_EMAIL || "hello@passedai.io"),
      name: poolSender.name,
    };
  }
  if (provider === "zeptomail") {
    if (isSelkaApp(appTag)) {
      return {
        email: process.env.ZEPTOMAIL_SELKA_SENDER_EMAIL || "selka@breakuprelief.com",
        name: poolSender.name || "Selka",
      };
    }
    if (String(appTag || "").toLowerCase() === "soulplan") {
      return {
        email:
          process.env.ZEPTOMAIL_SOULPLAN_SENDER_EMAIL ||
          process.env.ZEPTOMAIL_BREAKUP_SENDER_EMAIL ||
          "hello@breakuprelief.com",
        name: poolSender.name || "SoulPlan",
      };
    }
    if (isKaynelApp(appTag)) {
      const names = {
        ong: "ONG",
        sealed: "ONG",
        pupshape: "PupShape",
        kinbound: "Kinbound",
        volume_booster: "Volume Booster",
        smart_notes: "Smart Notes",
        ai_boyfriend: "AI Boyfriend",
        ai_girlfriend: "AI Girlfriend",
        onbrief: "Onbrief",
      };
      return {
        email: process.env.ZEPTOMAIL_ONG_SENDER_EMAIL || "hello@kaynel.solutions",
        name: poolSender.name || names[String(appTag || "").toLowerCase()] || "ONG",
      };
    }
    if (isOngApp(appTag)) {
      return {
        email: process.env.ZEPTOMAIL_ONG_SENDER_EMAIL || "hello@kaynel.solutions",
        name: poolSender.name || "ONG",
      };
    }
    if (isBreakupApp(appTag)) {
      return {
        email: process.env.ZEPTOMAIL_BREAKUP_SENDER_EMAIL || "hello@breakuprelief.com",
        name: poolSender.name || "Casey",
      };
    }
    return {
      email: process.env.ZEPTOMAIL_SENDER_EMAIL || "hello@thesisgenerator.io",
      name: process.env.ZEPTOMAIL_SENDER_NAME || poolSender.name || "Thesis Generator",
    };
  }
  return poolSender;
}

function sendViaResend(apiKey, fromEmail, fromName, toEmail, subject, html, appTag) {
  return new Promise((resolve, reject) => {
    const sender = resolveSender({email: fromEmail, name: fromName}, appTag);
    const payload = JSON.stringify({
      from: `${fromName} <${sender.email}>`,
      to: [toEmail],
      subject,
      html,
      reply_to: sender.email,
    });

    const options = {
      hostname: "api.resend.com",
      path: "/emails",
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode === 200 || res.statusCode === 201) {
          resolve(JSON.parse(data));
        } else {
          reject(new Error(`Resend ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

function sendViaMailgun(fromEmail, fromName, toEmail, subject, html, appTag) {
  return new Promise((resolve, reject) => {
    const apiKey = process.env.MAILGUN_API_KEY;
    const domain = process.env.MAILGUN_DOMAIN || "passedai.io";
    const sender = resolveSender({email: fromEmail, name: fromName}, appTag);
    const body = querystring.stringify({
      from: `${fromName} <${sender.email}>`,
      to: toEmail,
      subject,
      html,
      "h:Reply-To": sender.email,
    });

    const auth = Buffer.from(`api:${apiKey}`).toString("base64");
    const options = {
      hostname: "api.mailgun.net",
      path: `/v3/${domain}/messages`,
      method: "POST",
      headers: {
        Authorization: `Basic ${auth}`,
        "Content-Length": Buffer.byteLength(body),
        "Content-Type": "application/x-www-form-urlencoded",
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode === 200) {
          resolve(JSON.parse(data));
        } else {
          reject(new Error(`Mailgun ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

function sendViaSmtp2go(fromEmail, fromName, toEmail, subject, html, appTag) {
  return new Promise((resolve, reject) => {
    const apiKey = process.env.SMTP2GO_API_KEY;
    const sender = resolveSender({email: fromEmail, name: fromName}, appTag);
    const payload = JSON.stringify({
      sender: `${fromName} <${sender.email}>`,
      to: [toEmail],
      subject,
      html_body: html,
      custom_headers: [{header: "Reply-To", value: sender.email}],
    });

    const options = {
      hostname: "api.smtp2go.com",
      path: "/v3/email/send",
      method: "POST",
      headers: {
        "X-Smtp2go-Api-Key": apiKey,
        "Content-Type": "application/json",
        accept: "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode === 200) {
          resolve(JSON.parse(data));
        } else {
          reject(new Error(`SMTP2GO ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

function sendViaZeptomail(fromEmail, fromName, toEmail, subject, html, appTag) {
  return new Promise((resolve, reject) => {
    const apiKey = zeptomailApiKey(appTag);
    if (!apiKey) {
      reject(new Error("ZeptoMail API key not set (ZEPTOMAIL_BREAKUP_API_KEY or ZEPTOMAIL_API_KEY)"));
      return;
    }
    const apiUrl = new URL(process.env.ZEPTOMAIL_API_URL || "https://api.zeptomail.eu/v1.1/email");
    const sender = resolveSender({email: fromEmail, name: fromName}, appTag);
    const mimeHeaders = {
      "Reply-To": sender.email,
      "X-Tag-app": String(appTag || "fresh_start"),
    };
    const payload = JSON.stringify({
      from: {address: sender.email, name: fromName || sender.name},
      to: [{email_address: {address: toEmail, name: toEmail.split("@")[0] || "User"}}],
      subject,
      htmlbody: html,
      track_clicks: false,
      track_opens: false,
      mime_headers: mimeHeaders,
    });

    const options = {
      hostname: apiUrl.hostname,
      path: apiUrl.pathname,
      method: "POST",
      headers: {
        Authorization: `Zoho-enczapikey ${apiKey}`,
        Accept: "application/json",
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode === 200 || res.statusCode === 201) {
          resolve(JSON.parse(data || "{}"));
        } else {
          reject(new Error(`ZeptoMail ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

async function sendEmail({apiKey, fromEmail, fromName, toEmail, subject, html, appTag}) {
  if (isEmailSendingPaused()) {
    throw new Error("Email sending paused (EMAIL_SENDING_PAUSED)");
  }
  const provider = emailProvider();
  if (provider === "mailgun") {
    return sendViaMailgun(fromEmail, fromName, toEmail, subject, html, appTag);
  }
  if (provider === "smtp2go") {
    return sendViaSmtp2go(fromEmail, fromName, toEmail, subject, html, appTag);
  }
  if (provider === "zeptomail") {
    if (!isBreakupApp(appTag)) {
      throw new Error("ZeptoMail on Firebase — breakup/Selka apps only (use Supabase for thesis/predictify)");
    }
    return sendViaZeptomail(fromEmail, fromName, toEmail, subject, html, appTag);
  }
  return sendViaResend(apiKey, fromEmail, fromName, toEmail, subject, html, appTag);
}

module.exports = {
  emailProvider,
  hasEmailCredentials,
  resolveSender,
  sendEmail,
  isEmailSendingPaused,
  isBreakupApp,
};
