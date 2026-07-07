// Supabase Edge Function: check-new-users (v2)
// Processes ONE Firebase project per invocation using time-based round-robin.
// pg_cron fires every 5 minutes → each of 8 projects checked every ~40 minutes.
// Caps at 60 welcome emails per invocation to stay within edge function timeout.
// Accepts optional { "project": "project-id" } body to target a specific project.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// ── Config ──────────────────────────────────────────────────
const MAX_EMAILS_PER_RUN = 60;
const DEADLINE_MS = 50_000; // Stop processing at 50 seconds

// ── Firebase projects → app_id mapping ──────────────────────
const FIREBASE_PROJECTS: Record<
  string,
  { appId: string; multilingual: boolean; defaultLang: string; supportedLanguages: string[] }
> = {
  "thesis-generator-web": {
    appId: "thesis_generator",
    multilingual: true,
    defaultLang: "en",
    supportedLanguages: ["en", "ar", "fr", "es", "hi", "zh"],
  },
  // redflagscanner is intentionally NOT here. The Selka (Red Flag Scanner)
  // welcome email is handled by the dedicated `sendSelkaWelcome` Firebase
  // Cloud Function (firebase-welcome/functions/redflag/welcome.js) which
  // fires on users/{uid} create with localized, Selka-branded copy.
  // Listing redflagscanner here too would double-send: this Supabase
  // cron + the Firebase trigger both firing on the same signup.
  "breakuptherapy-e7dc0": {
    appId: "fresh_start",
    multilingual: false,
    defaultLang: "en",
    supportedLanguages: ["en"],
  },
  "soulplan-dateplanner": {
    appId: "soulplan",
    multilingual: true,
    defaultLang: "en",
    // Mirrors lib/services/locale_provider.dart in the SoulPlan Flutter app.
    // Language tags follow BCP 47 (Apple/Google/Superwall). The app writes
    // these tags directly to users/{uid}.language so this list must stay
    // in sync — add a language here when adding it to the Flutter app.
    supportedLanguages: ["en", "es", "fr", "pt", "de", "it", "pl", "tr", "ar", "ru", "hi", "id", "ja", "ko", "zh"],
  },
  petmealai: {
    appId: "pupshape",
    multilingual: false,
    defaultLang: "en",
    supportedLanguages: ["en"],
  },
  "parents-ai-e49a8": {
    appId: "kinbound",
    multilingual: true,
    defaultLang: "en",
    // Mirrors lib/core/localization/app_locales.dart in the Kinbound Flutter app.
    supportedLanguages: [
      "en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh",
      "ar", "hi", "id", "pl", "ru", "tr",
    ],
  },
  "predictify-3f30d": {
    appId: "predictify",
    multilingual: true,
    defaultLang: "en",
    supportedLanguages: ["en", "ar", "es", "fr", "pt", "de", "tr", "it", "pp", "hi", "id", "nl", "pl", "ja"],
  },
  // NBA Predictify intentionally not handled here: the predictify_v2 engine
  // (predictify-nba-emails workflow) now owns welcome / win-back / match-day
  // with proper cooldowns + bounce suppression. Keeping it here would double
  // welcome new NBA signups.
  "volume-booster-2f7bf": {
    appId: "volume_booster",
    multilingual: true,
    defaultLang: "en",
    supportedLanguages: ["en", "ar", "es", "fr", "zh", "hi", "pt", "ru"],
  },
  "horse-racing-f67e8": {
    appId: "horse_racing",
    multilingual: true,
    defaultLang: "en",
    supportedLanguages: ["en", "ar", "es", "fr"],
  },
  "boyfriend-ai-f1e5e": {
    appId: "ai_boyfriend",
    multilingual: true,
    defaultLang: "en",
    // Mirrors lib/l10n/app_localizations.dart kSupportedLanguages in the Flutter app.
    supportedLanguages: ["en", "es", "fr", "de", "it", "pt", "ar", "ja", "ko", "zh", "ru", "tr", "hi", "id", "pl", "nl"],
  },
  "apb412---ai-girlfriend-app": {
    appId: "ai_girlfriend",
    multilingual: true,
    defaultLang: "en",
    // Mirrors girlfriend_ai/lib/l10n kSupportedLanguages in the Flutter app.
    supportedLanguages: ["en", "es", "fr", "de", "it", "pt", "ar", "ja", "ko", "zh", "ru", "tr", "hi", "id", "pl", "nl"],
  },
  "audio-recorder-microphone": {
    appId: "smart_notes",
    multilingual: true,
    defaultLang: "en",
    // Mirrors Smart Notes app-localization codes.
    supportedLanguages: ["en", "es", "fr", "de", "pt", "it", "ar", "hi"],
  },
};

const PROJECT_IDS = Object.keys(FIREBASE_PROJECTS);

// Google OAuth2 client for Firebase CLI token exchange
const GOOGLE_CLIENT_ID =
  "563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com";
const GOOGLE_CLIENT_SECRET = "j9iVZfS8kkCEFUPaAeJV0sAi";

// ── Get access token from Firebase refresh token ────────────
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

  if (!res.ok) {
    throw new Error(`OAuth token exchange failed: ${res.status}`);
  }

  const data = await res.json();
  return data.access_token;
}

// ── List all users from a Firebase project ──────────────────
interface FirebaseUser {
  localId: string;
  email?: string;
  createdAt: string;
}

async function listFirebaseUsers(
  projectId: string,
  accessToken: string
): Promise<FirebaseUser[]> {
  const allUsers: FirebaseUser[] = [];
  let nextPageToken: string | undefined;

  do {
    const url = new URL(
      `https://identitytoolkit.googleapis.com/v1/projects/${projectId}/accounts:batchGet`
    );
    url.searchParams.set("maxResults", "500");
    if (nextPageToken) {
      url.searchParams.set("nextPageToken", nextPageToken);
    }

    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error(
        `Failed to list users for ${projectId}: ${res.status} ${errText}`
      );
      break;
    }

    const data = await res.json();
    const users = data.users || [];
    allUsers.push(...users);
    nextPageToken = data.nextPageToken;
  } while (nextPageToken);

  return allUsers;
}

// ── Language normalization map ──────────────────────────────
// The SoulPlan Flutter app uses BCP 47 tags (`pt-BR`, `zh-Hans`, etc.).
// We strip the variant after the dash/underscore and accept the base
// language since email templates are keyed by base language.
const LANG_NORMALIZE: Record<string, string> = {
  ar: "ar", arabic: "ar",
  es: "es", spanish: "es",
  fr: "fr", french: "fr",
  zh: "zh", chinese: "zh", zh_cn: "zh", zh_tw: "zh", zh_hans: "zh", zh_hant: "zh",
  hi: "hi", hindi: "hi",
  pt: "pt", portuguese: "pt", pt_br: "pt",
  ru: "ru", russian: "ru",
  en: "en", english: "en", en_us: "en",
  de: "de", german: "de", deutsch: "de",
  tr: "tr", turkish: "tr",
  it: "it", italian: "it", italiano: "it",
  pp: "pp", pt_pt: "pp",
  id: "id", indonesian: "id",
  nl: "nl", dutch: "nl", nederlands: "nl",
  pl: "pl", polish: "pl", polski: "pl",
  ja: "ja", japanese: "ja",
  ko: "ko", korean: "ko",
};

// ── Fetch user language + first name from Firestore via query ────────────
// One Firestore round-trip per user — read whatever personalisation signals
// the user doc carries (today: language, displayName).
async function fetchUserLocaleData(
  projectId: string,
  accessToken: string,
  email: string,
  supportedLanguages: string[]
): Promise<{ language: string; firstName?: string }> {
  try {
    const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents:runQuery`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        structuredQuery: {
          from: [{ collectionId: "users" }],
          where: {
            fieldFilter: {
              field: { fieldPath: "email" },
              op: "EQUAL",
              value: { stringValue: email },
            },
          },
          limit: 1,
        },
      }),
    });

    if (!res.ok) return { language: "en" };

    const results = await res.json();
    const doc = results?.[0]?.document;
    if (!doc?.fields) return { language: "en" };

    // First name = first word of displayName, trimmed.
    const displayName = (doc.fields.displayName?.stringValue ?? "").trim();
    const firstName = displayName ? displayName.split(/\s+/)[0] : undefined;

    const rawLang = doc.fields.language?.stringValue?.toLowerCase().trim();
    if (!rawLang) return { language: "en", firstName };

    const base = rawLang.split(/[_-]/)[0];
    const lang = LANG_NORMALIZE[base] || LANG_NORMALIZE[rawLang] || "en";
    return {
      language: supportedLanguages.includes(lang) ? lang : "en",
      firstName,
    };
  } catch {
    return { language: "en" };
  }
}

// (bulk fetchFirestoreLanguages removed — using per-user queries to stay within Firestore quota)

// ── Main handler ────────────────────────────────────────────
Deno.serve(async (req) => {
  // Allow pg_cron/pg_net calls (no CORS needed) + manual triggers
  if (req.method === "OPTIONS") {
    return new Response("ok", {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers":
          "authorization, x-client-info, apikey, content-type",
      },
    });
  }

  const startTime = Date.now();
  const deadline = startTime + DEADLINE_MS;
  const results: string[] = [];

  try {
    const FIREBASE_REFRESH_TOKEN = Deno.env.get("FIREBASE_REFRESH_TOKEN");
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
    const SUPABASE_SERVICE_ROLE_KEY =
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
    const FUNCTION_AUTH_KEY = Deno.env.get("FUNCTION_AUTH_KEY") || SUPABASE_SERVICE_ROLE_KEY;

    if (!FIREBASE_REFRESH_TOKEN) {
      return new Response(
        JSON.stringify({ error: "FIREBASE_REFRESH_TOKEN not configured" }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    // ── Determine which project to process ────────────────────
    let targetProjectId: string | undefined;
    try {
      const body = await req.json();
      if (body.project && FIREBASE_PROJECTS[body.project]) {
        targetProjectId = body.project;
      }
    } catch { /* no body or invalid JSON — use round-robin */ }

    if (!targetProjectId) {
      // Time-based round-robin: each 5-minute slot picks a different project
      const fiveMinSlot = Math.floor(Date.now() / (5 * 60 * 1000));
      const projectIndex = fiveMinSlot % PROJECT_IDS.length;
      targetProjectId = PROJECT_IDS[projectIndex];
    }

    const config = FIREBASE_PROJECTS[targetProjectId];
    results.push(`🎯 Processing: ${config.appId} (${targetProjectId})`);

    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

    // 1. Get Firebase access token
    const accessToken = await getAccessToken(FIREBASE_REFRESH_TOKEN);
    results.push("✅ Got Firebase access token");

    // 2. Get existing welcomed users for THIS project only
    const welcomedSet = new Set<string>();
    let offset = 0;
    const pageSize = 1000;

    while (true) {
      const { data: page, error: dbError } = await supabase
        .from("welcomed_users")
        .select("email")
        .eq("app_id", config.appId)
        .range(offset, offset + pageSize - 1);

      if (dbError) {
        throw new Error(`DB query failed: ${dbError.message}`);
      }

      for (const u of page || []) {
        welcomedSet.add(u.email);
      }

      if (!page || page.length < pageSize) break;
      offset += pageSize;
    }

    results.push(`📊 ${welcomedSet.size} already welcomed for ${config.appId}`);

    // 3. Language detection: per-user Firestore query (avoids bulk scan quota issues)
    // Individual queries cost 1 read per new user vs thousands for a full collection scan.

    // 4. List Firebase users for this project
    const users = await listFirebaseUsers(targetProjectId, accessToken);
    results.push(`👥 ${users.length} total Firebase users`);

    // 5. Process new users
    let totalNew = 0;
    let totalSent = 0;
    let totalSkipped = 0;
    let hitCap = false;
    let hitDeadline = false;

    for (const user of users) {
      // Check deadline
      if (Date.now() > deadline) {
        hitDeadline = true;
        results.push(`⏰ Hit ${DEADLINE_MS / 1000}s deadline — stopping`);
        break;
      }

      // Check email cap
      if (totalSent >= MAX_EMAILS_PER_RUN) {
        hitCap = true;
        results.push(`📬 Hit email cap (${MAX_EMAILS_PER_RUN}) — stopping`);
        break;
      }

      const email = user.email?.toLowerCase().trim();
      if (!email) continue;

      // Skip test accounts
      if (
        email.includes("cloudtestlabaccounts.com") ||
        email.includes("example.com")
      ) {
        continue;
      }

      if (welcomedSet.has(email)) continue;

      // New user found!
      totalNew++;

      // Rate limit: wait 600ms between emails (Resend allows 2/sec)
      if (totalSent > 0) {
        await new Promise((r) => setTimeout(r, 600));
      }

      // Look up language + firstName (per-user Firestore query — one round-trip).
      let language = config.defaultLang;
      let firstName: string | undefined;
      if (config.multilingual) {
        const data = await fetchUserLocaleData(
          targetProjectId,
          accessToken,
          email,
          config.supportedLanguages
        );
        language = data.language;
        firstName = data.firstName;
      }

      // Send welcome email
      try {
        const welcomeUrl = `${SUPABASE_URL}/functions/v1/welcome-email`;
        const welcomeRes = await fetch(welcomeUrl, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${FUNCTION_AUTH_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: email,
            app_id: config.appId,
            language: language,
            firstName: firstName, // welcome-email greeting personalisation
          }),
        });

        let welcomeData: Record<string, unknown>;
        try {
          welcomeData = await welcomeRes.json();
        } catch {
          welcomeData = { raw: await welcomeRes.text() };
        }

        if (welcomeRes.ok && welcomeData.success) {
          const { error: insertError } = await supabase
            .from("welcomed_users")
            .upsert(
              {
                email: email,
                app_id: config.appId,
                firebase_uid: user.localId,
                firebase_project: targetProjectId,
                language: language,
                welcomed_at: new Date().toISOString(),
              },
              { onConflict: "email,app_id" }
            );

          if (insertError) {
            console.error(`DB insert failed for ${email}: ${insertError.message}`);
          } else {
            totalSent++;
            welcomedSet.add(email);
          }
        } else if (welcomeData.bounced) {
          console.log(`BOUNCED: ${email} (${config.appId}) — marking in DB`);
          await supabase
            .from("welcomed_users")
            .upsert(
              {
                email: email,
                app_id: config.appId,
                firebase_uid: user.localId,
                firebase_project: targetProjectId,
                language: language,
                welcomed_at: new Date().toISOString(),
                bounced: true,
              },
              { onConflict: "email,app_id" }
            );
          welcomedSet.add(email);
          totalSkipped++;
        } else {
          console.error(
            `Welcome email failed for ${email}: status=${welcomeRes.status} response=${JSON.stringify(welcomeData)}`
          );
          if (totalSkipped === 0) {
            results.push(`❌ First failure: ${email} status=${welcomeRes.status} ${JSON.stringify(welcomeData).substring(0, 200)}`);
          }
          totalSkipped++;
        }
      } catch (sendErr) {
        console.error(`Error sending to ${email}: ${sendErr}`);
        totalSkipped++;
      }
    }

    const elapsed = Date.now() - startTime;
    const summary = {
      success: true,
      project: targetProjectId,
      app_id: config.appId,
      new_users_found: totalNew,
      welcome_emails_sent: totalSent,
      skipped: totalSkipped,
      hit_cap: hitCap,
      hit_deadline: hitDeadline,
      remaining: hitCap || hitDeadline ? totalNew - totalSent - totalSkipped : 0,
      elapsed_ms: elapsed,
      details: results,
    };

    console.log(JSON.stringify(summary));

    return new Response(JSON.stringify(summary), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("check-new-users error:", err);
    return new Response(
      JSON.stringify({
        error: "Internal error",
        message: String(err),
        details: results,
      }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
});
