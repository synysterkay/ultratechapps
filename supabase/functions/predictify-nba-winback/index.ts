// Supabase Edge Function: predictify-nba-winback
//
// Cohort cron for Predictify NBA. Finds users who signed in but have gone
// quiet for ~7 days (Firebase Auth lastRefreshAt) and fires the localized
// win-back email — the external trigger that re-enters the Hooked loop for a
// lapsing user. Mirrors check-new-users' Firebase access pattern.
//
// Schedule via pg_cron (e.g. once daily). Accepts an optional { "dry_run": true }
// body to count the cohort without sending.
//
// Dedup: the winback SENDER dedups lifetime on (uid, 'winback'), so re-runs
// never double-send. The [MIN,MAX] day window keeps us from re-POSTing
// long-dormant users every single run.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const FIREBASE_PROJECT = "nba-predictify";
const APP_ID = "predictify_nba";
const SUPPORTED_LANGUAGES = ["en", "ar", "es", "fr", "pt", "de", "tr", "it", "pp", "hi", "id", "nl", "pl", "ja"];

const LAPSED_MIN_DAYS = 7;   // start nudging after a week quiet
const LAPSED_MAX_DAYS = 14;  // stop after two weeks (sender dedup also guards)
const MAX_EMAILS_PER_RUN = 60;
const DEADLINE_MS = 50_000;
const DAY_MS = 24 * 60 * 60 * 1000;

// Firebase CLI OAuth client — same token-exchange path as check-new-users.
const GOOGLE_CLIENT_ID =
  "563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com";
const GOOGLE_CLIENT_SECRET = "j9iVZfS8kkCEFUPaAeJV0sAi";

const LANG_NORMALIZE: Record<string, string> = {
  ar: "ar", es: "es", fr: "fr", hi: "hi", pt: "pt", en: "en", de: "de",
  tr: "tr", it: "it", pp: "pp", pt_pt: "pp", id: "id", nl: "nl", pl: "pl", ja: "ja",
};

async function getAccessToken(refreshToken: string): Promise<string> {
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: GOOGLE_CLIENT_ID,
      client_secret: GOOGLE_CLIENT_SECRET,
      refresh_token: refreshToken,
      grant_type: "refresh_token",
    }),
  });
  if (!res.ok) throw new Error(`OAuth token exchange failed: ${res.status}`);
  return (await res.json()).access_token;
}

interface FbUser {
  localId: string;
  email?: string;
  displayName?: string;
  createdAt?: string;       // epoch ms (string)
  lastLoginAt?: string;     // epoch ms (string)
  lastRefreshAt?: string;   // ISO timestamp — most recent token refresh
}

async function listFirebaseUsers(projectId: string, accessToken: string): Promise<FbUser[]> {
  const all: FbUser[] = [];
  let nextPageToken: string | undefined;
  do {
    const url = new URL(
      `https://identitytoolkit.googleapis.com/v1/projects/${projectId}/accounts:batchGet`,
    );
    url.searchParams.set("maxResults", "500");
    if (nextPageToken) url.searchParams.set("nextPageToken", nextPageToken);
    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) {
      console.error(`listFirebaseUsers ${projectId}: ${res.status} ${await res.text()}`);
      break;
    }
    const data = await res.json();
    all.push(...(data.users || []));
    nextPageToken = data.nextPageToken;
  } while (nextPageToken);
  return all;
}

async function fetchUserLanguage(
  projectId: string,
  accessToken: string,
  email: string,
): Promise<string> {
  try {
    const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents:runQuery`;
    const res = await fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        structuredQuery: {
          from: [{ collectionId: "users" }],
          where: {
            fieldFilter: { field: { fieldPath: "email" }, op: "EQUAL", value: { stringValue: email } },
          },
          limit: 1,
        },
      }),
    });
    if (!res.ok) return "en";
    const results = await res.json();
    const raw = results?.[0]?.document?.fields?.language?.stringValue?.toLowerCase().trim();
    if (!raw) return "en";
    const base = raw.split(/[_-]/)[0];
    const lang = LANG_NORMALIZE[raw] || LANG_NORMALIZE[base] || "en";
    return SUPPORTED_LANGUAGES.includes(lang) ? lang : "en";
  } catch {
    return "en";
  }
}

// Most-recent-activity timestamp in ms. lastRefreshAt (ISO) is the best proxy
// for "opened the app"; fall back to lastLoginAt (epoch ms) then createdAt.
function lastActiveMs(u: FbUser): number | null {
  if (u.lastRefreshAt) {
    const t = Date.parse(u.lastRefreshAt);
    if (!Number.isNaN(t)) return t;
  }
  if (u.lastLoginAt) {
    const t = parseInt(u.lastLoginAt, 10);
    if (!Number.isNaN(t)) return t;
  }
  if (u.createdAt) {
    const t = parseInt(u.createdAt, 10);
    if (!Number.isNaN(t)) return t;
  }
  return null;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
      },
    });
  }

  const start = Date.now();
  const deadline = start + DEADLINE_MS;

  let dryRun = false;
  try {
    const body = await req.json();
    dryRun = body?.dry_run === true;
  } catch { /* no body */ }

  try {
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
    const FN_AUTH = Deno.env.get("FUNCTION_AUTH_KEY") || SERVICE_KEY;
    const REFRESH = Deno.env.get("FIREBASE_REFRESH_TOKEN");
    if (!REFRESH) {
      return new Response(JSON.stringify({ error: "FIREBASE_REFRESH_TOKEN not configured" }), {
        status: 500, headers: { "Content-Type": "application/json" },
      });
    }

    const accessToken = await getAccessToken(REFRESH);
    const users = await listFirebaseUsers(FIREBASE_PROJECT, accessToken);

    const now = Date.now();
    let candidates = 0;
    let sent = 0;
    let skipped = 0;
    let hitCap = false;
    let hitDeadline = false;

    for (const u of users) {
      if (Date.now() > deadline) { hitDeadline = true; break; }
      if (sent >= MAX_EMAILS_PER_RUN) { hitCap = true; break; }

      const email = u.email?.toLowerCase().trim();
      if (!email) continue;
      if (email.includes("cloudtestlabaccounts.com") || email.includes("example.com")) continue;

      const active = lastActiveMs(u);
      if (active === null) continue;
      const days = (now - active) / DAY_MS;
      if (days < LAPSED_MIN_DAYS || days > LAPSED_MAX_DAYS) continue;

      candidates++;
      if (dryRun) continue;

      // Rate limit: Resend allows ~2/sec; the sender also throttles itself.
      if (sent > 0) await new Promise((r) => setTimeout(r, 600));

      const language = await fetchUserLanguage(FIREBASE_PROJECT, accessToken, email);
      const firstName = (u.displayName || "").trim().split(/\s+/)[0] || "";

      try {
        const res = await fetch(`${SUPABASE_URL}/functions/v1/predictify-nba-winback-email`, {
          method: "POST",
          headers: { Authorization: `Bearer ${FN_AUTH}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            uid: u.localId,
            email,
            language,
            ...(firstName ? { first_name: firstName } : {}),
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && (data.ok || data.id || data.duplicate || data.skipped)) {
          if (data.id) sent++; else skipped++; // duplicate/suppressed = not a fresh send
        } else {
          skipped++;
          console.error(`winback send failed ${email}: ${res.status} ${JSON.stringify(data).slice(0, 200)}`);
        }
      } catch (e) {
        skipped++;
        console.error(`winback send error ${email}: ${e}`);
      }
    }

    const summary = {
      success: true, app_id: APP_ID, project: FIREBASE_PROJECT,
      total_users: users.length, lapsed_candidates: candidates,
      emails_sent: sent, skipped, dry_run: dryRun,
      window_days: [LAPSED_MIN_DAYS, LAPSED_MAX_DAYS],
      hit_cap: hitCap, hit_deadline: hitDeadline, elapsed_ms: Date.now() - start,
    };
    console.log(JSON.stringify(summary));
    return new Response(JSON.stringify(summary), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("predictify-nba-winback error:", err);
    return new Response(JSON.stringify({ error: "Internal error", message: String(err) }), {
      status: 500, headers: { "Content-Type": "application/json" },
    });
  }
});
