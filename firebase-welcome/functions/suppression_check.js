/**
 * Check Supabase email_suppressions before Firebase sends (Selka path).
 * Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY on the Firebase project.
 */

const https = require("https");

function supabaseConfig() {
  const url = (process.env.SUPABASE_URL || "").replace(/\/$/, "");
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!url || !key) return null;
  return {url, key};
}

function supabaseGet(path, cfg) {
  return new Promise((resolve, reject) => {
    const u = new URL(`${cfg.url}/rest/v1/${path}`);
    const options = {
      hostname: u.hostname,
      path: `${u.pathname}${u.search}`,
      method: "GET",
      headers: {
        apikey: cfg.key,
        Authorization: `Bearer ${cfg.key}`,
      },
    };
    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(data || "[]"));
          } catch {
            resolve([]);
          }
        } else {
          reject(new Error(`Supabase ${res.statusCode}: ${data.slice(0, 200)}`));
        }
      });
    });
    req.on("error", reject);
    req.end();
  });
}

/**
 * @param {string} email
 * @param {string} app e.g. red_flag_scanner
 * @returns {Promise<boolean>}
 */
async function isRecipientBlocked(email, app) {
  const cfg = supabaseConfig();
  if (!cfg) return false;

  const recipient = String(email || "").toLowerCase().trim();
  if (!recipient) return false;

  for (const appSlug of [app, "*", "global"]) {
    const path =
      `email_suppressions?recipient=eq.${encodeURIComponent(recipient)}` +
      `&app=eq.${encodeURIComponent(appSlug)}&select=recipient&limit=1`;
    try {
      const rows = await supabaseGet(path, cfg);
      if (Array.isArray(rows) && rows.length > 0) return true;
    } catch (err) {
      console.warn(`suppression_check failed (${appSlug}):`, err.message);
    }
  }
  return false;
}

module.exports = {isRecipientBlocked};
