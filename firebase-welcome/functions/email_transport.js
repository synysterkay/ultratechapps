/**
 * Pluggable email transport for Firebase Cloud Functions.
 * Set EMAIL_PROVIDER=mailgun to pin sends to passedai.io.
 */

const https = require("https");
const querystring = require("querystring");

function emailProvider() {
  return (process.env.EMAIL_PROVIDER || "resend").toLowerCase() === "mailgun" ? "mailgun" : "resend";
}

function hasEmailCredentials(apiKey) {
  if (emailProvider() === "mailgun") {
    return !!(process.env.MAILGUN_API_KEY && process.env.MAILGUN_DOMAIN);
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
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": Buffer.byteLength(body),
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

async function sendEmail({apiKey, fromEmail, fromName, toEmail, subject, html}) {
  if (emailProvider() === "mailgun") {
    return sendViaMailgun(fromEmail, fromName, toEmail, subject, html);
  }
  return sendViaResend(apiKey, fromEmail, fromName, toEmail, subject, html);
}

module.exports = {emailProvider, hasEmailCredentials, resolveSender, sendEmail};
