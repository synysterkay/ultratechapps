// Supabase Edge Function: predictify-nba-gameday
//
// Game-day cohort cron for Predictify NBA. On nights with NBA games it nudges
// users who've drifted a few days (2–6) back into the app — the recurring
// external trigger of the Hooked loop. Skips entirely on no-game days.
//
// Schedule via pg_cron in the early evening (US time), e.g. 2–3x/week — the
// cron cadence controls how often the nudge goes out; the sender also dedups
// per-day so a user never gets more than one game-day email in a day.
//
// Cohort: lastRefreshAt 2–6 days ago. Active-today users are already in the
// app (skipped); 7–14 day users are handled by predictify-nba-winback.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const FIREBASE_PROJECT = "nba-predictify";
const APP_ID = "predictify_nba";
const SUPPORTED_LANGUAGES = ["en", "ar", "es", "fr", "pt", "de", "tr", "it", "pp", "hi", "id", "nl", "pl", "ja"];

const ACTIVE_MIN_DAYS = 2;  // not in the app today/yesterday…
const ACTIVE_MAX_DAYS = 6;  // …but not yet win-back territory (7+)
const MAX_EMAILS_PER_RUN = 60;
const DEADLINE_MS = 50_000;
const DAY_MS = 24 * 60 * 60 * 1000;

const NBA_SCOREBOARD_URL =
  "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json";

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
  createdAt?: string;
  lastLoginAt?: string;
  lastRefreshAt?: string;
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
    const res = await fetch(url.toString(), { headers: { Authorization: `Bearer ${accessToken}` } });
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

async function fetchUserLanguage(projectId: string, accessToken: string, email: string): Promise<string> {
  try {
    const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents:runQuery`;
    const res = await fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        structuredQuery: {
          from: [{ collectionId: "users" }],
          where: { fieldFilter: { field: { fieldPath: "email" }, op: "EQUAL", value: { stringValue: email } } },
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

function lastActiveMs(u: FbUser): number | null {
  if (u.lastRefreshAt) {
    const t = Date.parse(u.lastRefreshAt);
    if (!Number.isNaN(t)) return t;
  }
  if (u.lastLoginAt) {
    const t = parseInt(u.lastLoginAt, 10);
    if (!Number.isNaN(t)) return t;
  }
  return null;
}

// Returns { count, gameDate } for today's NBA slate, or { count: 0 } off-days.
async function fetchTodaysGames(): Promise<{ count: number; gameDate: string }> {
  try {
    const res = await fetch(NBA_SCOREBOARD_URL, { headers: { "User-Agent": "predictify-nba-cron" } });
    if (!res.ok) return { count: 0, gameDate: "" };
    const data = await res.json();
    const games = data?.scoreboard?.games ?? [];
    const gameDate = (data?.scoreboard?.gameDate ?? "").slice(0, 10);
    return { count: Array.isArray(games) ? games.length : 0, gameDate };
  } catch (e) {
    console.error("fetchTodaysGames error:", e);
    return { count: 0, gameDate: "" };
  }
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
  let force = false;
  try {
    const body = await req.json();
    dryRun = body?.dry_run === true;
    force = body?.force === true; // bypass the games-today gate for testing
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

    // Gate: only run on nights with NBA games (unless forced for testing).
    const { count: gamesToday, gameDate } = await fetchTodaysGames();
    const dedupDate = gameDate || new Date().toISOString().slice(0, 10);
    if (gamesToday === 0 && !force) {
      const summary = { success: true, app_id: APP_ID, games_today: 0, emails_sent: 0, note: "no games today — skipped" };
      console.log(JSON.stringify(summary));
      return new Response(JSON.stringify(summary), { status: 200, headers: { "Content-Type": "application/json" } });
    }

    const accessToken = await getAccessToken(REFRESH);
    const users = await listFirebaseUsers(FIREBASE_PROJECT, accessToken);

    const now = Date.now();
    let candidates = 0, sent = 0, skipped = 0;
    let hitCap = false, hitDeadline = false;

    for (const u of users) {
      if (Date.now() > deadline) { hitDeadline = true; break; }
      if (sent >= MAX_EMAILS_PER_RUN) { hitCap = true; break; }

      const email = u.email?.toLowerCase().trim();
      if (!email) continue;
      if (email.includes("cloudtestlabaccounts.com") || email.includes("example.com")) continue;

      const active = lastActiveMs(u);
      if (active === null) continue;
      const days = (now - active) / DAY_MS;
      if (days < ACTIVE_MIN_DAYS || days > ACTIVE_MAX_DAYS) continue;

      candidates++;
      if (dryRun) continue;

      if (sent > 0) await new Promise((r) => setTimeout(r, 600));

      const language = await fetchUserLanguage(FIREBASE_PROJECT, accessToken, email);
      const firstName = (u.displayName || "").trim().split(/\s+/)[0] || "";

      try {
        const res = await fetch(`${SUPABASE_URL}/functions/v1/predictify-nba-gameday-email`, {
          method: "POST",
          headers: { Authorization: `Bearer ${FN_AUTH}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            uid: u.localId,
            email,
            language,
            dedup_date: dedupDate,
            ...(firstName ? { first_name: firstName } : {}),
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && (data.id || data.duplicate || data.skipped)) {
          if (data.id) sent++; else skipped++;
        } else {
          skipped++;
          console.error(`gameday send failed ${email}: ${res.status} ${JSON.stringify(data).slice(0, 200)}`);
        }
      } catch (e) {
        skipped++;
        console.error(`gameday send error ${email}: ${e}`);
      }
    }

    const summary = {
      success: true, app_id: APP_ID, games_today: gamesToday, game_date: dedupDate,
      total_users: users.length, drifting_candidates: candidates,
      emails_sent: sent, skipped, dry_run: dryRun, forced: force,
      window_days: [ACTIVE_MIN_DAYS, ACTIVE_MAX_DAYS],
      hit_cap: hitCap, hit_deadline: hitDeadline, elapsed_ms: Date.now() - start,
    };
    console.log(JSON.stringify(summary));
    return new Response(JSON.stringify(summary), { status: 200, headers: { "Content-Type": "application/json" } });
  } catch (err) {
    console.error("predictify-nba-gameday error:", err);
    return new Response(JSON.stringify({ error: "Internal error", message: String(err) }), {
      status: 500, headers: { "Content-Type": "application/json" },
    });
  }
});
