// Supabase Edge Function: check-new-users
// Polls Firebase Auth across all 7 projects every 5 minutes.
// Finds new users not yet in welcomed_users table → sends welcome email via welcome-email function.
// Triggered by pg_cron via pg_net HTTP call.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// ── Firebase projects → app_id mapping ──────────────────────
const FIREBASE_PROJECTS: Record<
  string,
  { appId: string; multilingual: boolean; defaultLang: string; supportedLanguages: string[] }
> = {
  "thesis-generator-web": {
    appId: "thesis_generator",
    multilingual: false,
    defaultLang: "en",
    supportedLanguages: ["en"],
  },
  redflagscanner: {
    appId: "redflag_scanner",
    multilingual: false,
    defaultLang: "en",
    supportedLanguages: ["en"],
  },
  "breakuptherapy-e7dc0": {
    appId: "fresh_start",
    multilingual: false,
    defaultLang: "en",
    supportedLanguages: ["en"],
  },
  "soulplan-dateplanner": {
    appId: "soulplan",
    multilingual: false,
    defaultLang: "en",
    supportedLanguages: ["en"],
  },
  petmealai: {
    appId: "pupshape",
    multilingual: false,
    defaultLang: "en",
    supportedLanguages: ["en"],
  },
  "predictify-3f30d": {
    appId: "predictify",
    multilingual: true,
    defaultLang: "en",
    supportedLanguages: ["en", "ar", "es", "fr"],
  },
  "volume-booster-2f7bf": {
    appId: "volume_booster",
    multilingual: true,
    defaultLang: "en",
    supportedLanguages: ["en", "es", "fr", "zh", "hi", "pt", "ru"],
  },
};

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
const LANG_NORMALIZE: Record<string, string> = {
  ar: "ar", arabic: "ar",
  es: "es", spanish: "es",
  fr: "fr", french: "fr",
  zh: "zh", chinese: "zh", zh_cn: "zh", zh_tw: "zh",
  hi: "hi", hindi: "hi",
  pt: "pt", portuguese: "pt", pt_br: "pt",
  ru: "ru", russian: "ru",
  en: "en", english: "en", en_us: "en",
};

// ── Fetch user languages from Firestore for a project ───────
async function fetchFirestoreLanguages(
  projectId: string,
  accessToken: string,
  supportedLanguages: string[]
): Promise<Map<string, string>> {
  const emailToLang = new Map<string, string>();
  const baseUrl = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/users`;
  let pageToken: string | undefined;

  do {
    const url = new URL(baseUrl);
    url.searchParams.set("pageSize", "300");
    if (pageToken) url.searchParams.set("pageToken", pageToken);

    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    if (!res.ok) {
      console.error(`Firestore fetch failed for ${projectId}: ${res.status}`);
      break;
    }

    const data = await res.json();
    const docs = data.documents || [];

    for (const doc of docs) {
      const fields = doc.fields || {};
      const email = fields.email?.stringValue?.toLowerCase().trim();
      if (!email) continue;

      let lang = "en";
      const rawLang = fields.language?.stringValue?.toLowerCase().trim();
      if (rawLang) {
        // Normalize: strip locale suffixes like en_US, zh-Hans
        const base = rawLang.split(/[_-]/)[0];
        lang = LANG_NORMALIZE[base] || LANG_NORMALIZE[rawLang] || "en";
      }

      // Only keep languages this app actually supports
      if (!supportedLanguages.includes(lang)) lang = "en";
      emailToLang.set(email, lang);
    }

    pageToken = data.nextPageToken;
  } while (pageToken);

  return emailToLang;
}

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
  const results: string[] = [];

  try {
    const FIREBASE_REFRESH_TOKEN = Deno.env.get("FIREBASE_REFRESH_TOKEN");
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
    const SUPABASE_SERVICE_ROLE_KEY =
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
    // For function-to-function calls (SUPABASE_ prefix vars can't be overridden)
    const FUNCTION_AUTH_KEY = Deno.env.get("FUNCTION_AUTH_KEY") || SUPABASE_SERVICE_ROLE_KEY;

    if (!FIREBASE_REFRESH_TOKEN) {
      return new Response(
        JSON.stringify({ error: "FIREBASE_REFRESH_TOKEN not configured" }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

    // 1. Get Firebase access token
    const accessToken = await getAccessToken(FIREBASE_REFRESH_TOKEN);
    results.push("✅ Got Firebase access token");

    // 2. Get all existing welcomed users from DB (paginate past the 1000 row limit)
    const welcomedSet = new Set<string>();
    let offset = 0;
    const pageSize = 1000;

    while (true) {
      const { data: page, error: dbError } = await supabase
        .from("welcomed_users")
        .select("email, app_id")
        .range(offset, offset + pageSize - 1);

      if (dbError) {
        throw new Error(`DB query failed: ${dbError.message}`);
      }

      for (const u of page || []) {
        welcomedSet.add(`${u.email}|${u.app_id}`);
      }

      if (!page || page.length < pageSize) break;
      offset += pageSize;
    }

    results.push(`📊 ${welcomedSet.size} users already welcomed`);

    // 3. Prefetch Firestore languages for multilingual projects
    const languageMaps = new Map<string, Map<string, string>>();
    for (const [projectId, config] of Object.entries(FIREBASE_PROJECTS)) {
      if (config.multilingual) {
        try {
          const langMap = await fetchFirestoreLanguages(
            projectId,
            accessToken,
            config.supportedLanguages
          );
          languageMaps.set(projectId, langMap);
          results.push(`🌍 ${config.appId}: ${langMap.size} user languages loaded from Firestore`);
        } catch (err) {
          console.error(`Firestore language fetch failed for ${projectId}: ${err}`);
          results.push(`⚠️ ${config.appId}: language fetch failed, defaulting to en`);
        }
      }
    }

    // 4. Check each Firebase project
    let totalNew = 0;
    let totalSent = 0;
    let totalSkipped = 0;

    for (const [projectId, config] of Object.entries(FIREBASE_PROJECTS)) {
      try {
        const users = await listFirebaseUsers(projectId, accessToken);
        let projectNew = 0;

        for (const user of users) {
          const email = user.email?.toLowerCase().trim();
          if (!email) continue;

          // Skip test accounts
          if (
            email.includes("cloudtestlabaccounts.com") ||
            email.includes("example.com")
          ) {
            continue;
          }

          const key = `${email}|${config.appId}`;
          if (welcomedSet.has(key)) continue;

          // New user found!
          projectNew++;
          totalNew++;

          // Rate limit: wait 600ms between emails (Resend allows 2/sec)
          if (totalNew > 1) {
            await new Promise((r) => setTimeout(r, 600));
          }

          // Look up language from Firestore for multilingual apps
          let language = config.defaultLang;
          if (config.multilingual) {
            const langMap = languageMaps.get(projectId);
            if (langMap) {
              language = langMap.get(email) || config.defaultLang;
            }
          }

          // Send welcome email via the welcome-email function
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
                }),
              }
            );

            let welcomeData: Record<string, unknown>;
            try {
              welcomeData = await welcomeRes.json();
            } catch {
              welcomeData = { raw: await welcomeRes.text() };
            }

            if (welcomeRes.ok && welcomeData.success) {
              // Record in database
              const { error: insertError } = await supabase
                .from("welcomed_users")
                .upsert(
                  {
                    email: email,
                    app_id: config.appId,
                    firebase_uid: user.localId,
                    firebase_project: projectId,
                    language: language,
                    welcomed_at: new Date().toISOString(),
                  },
                  { onConflict: "email,app_id" }
                );

              if (insertError) {
                console.error(
                  `DB insert failed for ${email}: ${insertError.message}`
                );
              } else {
                totalSent++;
                // Add to set so we don't re-process within this run
                welcomedSet.add(key);
              }
            } else {
              console.error(
                `Welcome email failed for ${email} (${config.appId}): status=${welcomeRes.status} response=${JSON.stringify(welcomeData)}`
              );
              if (totalSkipped === 0) {
                results.push(`❌ First failure: ${email} (${config.appId}) status=${welcomeRes.status} ${JSON.stringify(welcomeData).substring(0, 200)}`);
              }
              totalSkipped++;
            }
          } catch (sendErr) {
            console.error(`Error sending to ${email}: ${sendErr}`);
            totalSkipped++;
          }
        }

        results.push(
          `${config.appId}: ${users.length} total, ${projectNew} new`
        );
      } catch (projErr) {
        results.push(`❌ ${config.appId}: ${projErr}`);
      }
    }

    const elapsed = Date.now() - startTime;
    const summary = {
      success: true,
      new_users_found: totalNew,
      welcome_emails_sent: totalSent,
      skipped: totalSkipped,
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
