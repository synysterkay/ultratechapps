/**
 * Pluggable email transport for Firebase Cloud Functions.
 * EMAIL_PROVIDER: resend | mailgun | smtp2go
 */

const https = require("https");
const querystring = require("querystring");

function emailProvider() {
  const p = (process.env.EMAIL_PROVIDER || "resend").toLowerCase();
  if (p === "mailgun") return "mailgun";
  if (p === "smtp2go") return "smtp2go";
  return "resend";
}

function isEmailSendingPaused() {
  const v = (process.env.EMAIL_SENDING_PAUSED || "").toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

function hasEmailCredentials(apiKey) {
  const provider = emailProvider();
  if (provider === "mailgun") {
    return !!(process.env.MAILGUN_API_KEY && process.env.MAILGUN_DOMAIN);
  }
  if (provider === "smtp2go") {
    return !!process.env.SMTP2GO_API_KEY;
  }
  return !!apiKey;
}

function resolveSender(poolSender) {
  if (emailProvider() !== "mailgun") return poolSender;
  const isSelka = String(poolSender.email || "").toLowerCase().startsWith("selka@");
  return {
    email: isSelka
      ? (process.env.MAILGUN_SELKA_SENDER_EMAIL || "selka@passedai.io")
      : (process.env.MAILGUN_SENDER_EMAIL || "hello@passedai.io"),
    name: poolSender.name,
  };
}

function sendViaResend(apiKey, fromEmail, fromName, toEmail, subject, html) {
  return new Promise((resolve, reject) => {
    const sender = resolveSender({email: fromEmail, name: fromName});
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

function sendViaMailgun(fromEmail, fromName, toEmail, subject, html) {
  return new Promise((resolve, reject) => {
    const apiKey = process.env.MAILGUN_API_KEY;
    const domain = process.env.MAILGUN_DOMAIN || "passedai.io";
    const sender = resolveSender({email: fromEmail, name: fromName});
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

function sendViaSmtp2go(fromEmail, fromName, toEmail, subject, html) {
  return new Promise((resolve, reject) => {
    const apiKey = process.env.SMTP2GO_API_KEY;
    const sender = resolveSender({email: fromEmail, name: fromName});
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

async function sendEmail({apiKey, fromEmail, fromName, toEmail, subject, html}) {
  if (isEmailSendingPaused()) {
    throw new Error("Email sending paused (EMAIL_SENDING_PAUSED)");
  }
  const provider = emailProvider();
  if (provider === "mailgun") {
    return sendViaMailgun(fromEmail, fromName, toEmail, subject, html);
  }
  if (provider === "smtp2go") {
    return sendViaSmtp2go(fromEmail, fromName, toEmail, subject, html);
  }
  return sendViaResend(apiKey, fromEmail, fromName, toEmail, subject, html);
}

module.exports = {emailProvider, hasEmailCredentials, resolveSender, sendEmail, isEmailSendingPaused};
