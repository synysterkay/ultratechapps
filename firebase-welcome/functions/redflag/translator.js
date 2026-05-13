/**
 * Translate-at-send + Firestore cache for Selka emails.
 *
 * Why this design vs. pre-translating every template into every locale:
 *   - Templates are content; they change. Re-translating 30 emails × 17
 *     locales every edit is wasteful and easy to forget.
 *   - First user in each locale pays a one-time ~1.5s DeepSeek latency.
 *     Every user after them gets the cached translation instantly.
 *   - Cache is global (Firestore collection `email_translations`), not
 *     per-user. So if one Spanish user triggers the welcome, the next
 *     ten thousand Spanish users hit the cache.
 *
 * Cache key: SHA-256 of (templateId, version, sourceLocale, targetLocale,
 *                       sourceText). The version bump in templates.js
 *                       invalidates the cache on copy changes.
 *
 * Source-of-truth language is English; targets are the 17 other locales
 * the app ships in. Names match the easy_localization codes in the app.
 */

const crypto = require("crypto");
const admin = require("firebase-admin");

const SOURCE_LOCALE = "en";

const LANGUAGE_NAMES = {
  en: "English",
  es: "Spanish",
  pt: "Portuguese",
  fr: "French",
  de: "German",
  it: "Italian",
  nl: "Dutch",
  pl: "Polish",
  tr: "Turkish",
  id: "Indonesian",
  vi: "Vietnamese",
  ru: "Russian",
  uk: "Ukrainian",
  ar: "Arabic",
  hi: "Hindi",
  ja: "Japanese",
  ko: "Korean",
  zh: "Chinese (Simplified)",
};

const RTL_LOCALES = new Set(["ar", "he", "fa", "ur"]);

const DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions";
const DEEPSEEK_MODEL = "deepseek-chat";

// Locale tags like en_US, pt_BR — squash to base + sanitize. Anything
// outside the supported set falls back to English.
function normalizeLocale(raw) {
  if (!raw) return SOURCE_LOCALE;
  const base = String(raw).split("_")[0].split("-")[0].toLowerCase();
  return LANGUAGE_NAMES[base] ? base : SOURCE_LOCALE;
}

function isRtl(locale) {
  return RTL_LOCALES.has(normalizeLocale(locale));
}

/**
 * Translate a single template field into the target locale, with cache.
 *
 * @param {Object} args
 * @param {string} args.templateId      e.g. "welcome.subject"
 * @param {number} args.version          template version (bump to invalidate)
 * @param {string} args.text              source English text (no interpolation yet)
 * @param {string} args.targetLocale     2-letter locale code
 * @param {string} args.deepseekApiKey   API key (from Firebase secret)
 * @returns {Promise<string>}             translated text
 */
async function translateField({templateId, version, text, targetLocale, deepseekApiKey}) {
  const locale = normalizeLocale(targetLocale);
  if (locale === SOURCE_LOCALE) return text;

  const hash = cacheKey({templateId, version, sourceLocale: SOURCE_LOCALE,
    targetLocale: locale, text});
  const ref = admin.firestore().collection("email_translations").doc(hash);

  const cached = await ref.get();
  if (cached.exists) {
    return cached.data().translated;
  }

  const translated = await callDeepseek({text, targetLocale: locale,
    apiKey: deepseekApiKey});

  // Write-through. If two functions race we accept the latter — both are
  // valid translations and the doc is immutable to clients via rules.
  await ref.set({
    template_id: templateId,
    version,
    source_locale: SOURCE_LOCALE,
    target_locale: locale,
    original: text,
    translated,
    created_at: admin.firestore.FieldValue.serverTimestamp(),
  }, {merge: false});

  return translated;
}

/**
 * Translate every field of a whole template object at once. The cache key
 * is per-field so partial-translation hits are reused.
 *
 * @param {Object} template  template entry from templates.js
 * @param {string} templateId  template name (used as cache key prefix)
 * @param {string} targetLocale
 * @param {string} deepseekApiKey
 * @returns {Promise<Object>}  same shape as template, but localized
 */
async function translateTemplate(template, templateId, targetLocale, deepseekApiKey) {
  const locale = normalizeLocale(targetLocale);
  if (locale === SOURCE_LOCALE) return template;

  const out = {...template};

  const fieldKeys = ["subject", "preheader", "cta", "ps"];
  await Promise.all(fieldKeys.map(async (key) => {
    if (!template[key]) return;
    out[key] = await translateField({
      templateId: `${templateId}.${key}`,
      version: template.version || 1,
      text: template[key],
      targetLocale: locale,
      deepseekApiKey,
    });
  }));

  // Body is an array of paragraphs. Translate them as a single batch
  // call so the model preserves voice consistency across paragraphs.
  if (Array.isArray(template.body) && template.body.length > 0) {
    out.body = await translateBody({
      templateId: `${templateId}.body`,
      version: template.version || 1,
      paragraphs: template.body,
      targetLocale: locale,
      deepseekApiKey,
    });
  }

  return out;
}

// Body translation is batched (one DeepSeek call per template-locale pair)
// so a single template renders into a new locale in ~1.5s instead of N×.
async function translateBody({templateId, version, paragraphs, targetLocale, deepseekApiKey}) {
  const joined = paragraphs.join("\n\n%%PARA_BREAK%%\n\n");
  const translatedJoined = await translateField({
    templateId,
    version,
    text: joined,
    targetLocale,
    deepseekApiKey,
  });
  return translatedJoined
      .split("%%PARA_BREAK%%")
      .map((p) => p.trim())
      .filter((p) => p.length > 0);
}

function cacheKey({templateId, version, sourceLocale, targetLocale, text}) {
  const payload = JSON.stringify({templateId, version, sourceLocale,
    targetLocale, text});
  return crypto.createHash("sha256").update(payload).digest("hex");
}

async function callDeepseek({text, targetLocale, apiKey}) {
  const langName = LANGUAGE_NAMES[targetLocale] || "English";
  const systemPrompt =
      "You are a professional email localization translator for a relationship-" +
      "analysis app called Selka. Translate the user's text into " + langName +
      ". Rules:\n" +
      "- Keep all {placeholders} EXACTLY as-is — do not translate them, " +
      "do not add or remove braces.\n" +
      "- Keep markdown emphasis (**bold**, *italic*) intact.\n" +
      "- Preserve `%%PARA_BREAK%%` markers exactly where they appear.\n" +
      "- Preserve line breaks and paragraph structure.\n" +
      "- Keep the proper noun 'Selka' untranslated.\n" +
      "- Voice: warm, sharp, direct relationship coach. Match the source " +
      "tone, not a literal translation. Use the informal 'you' form when " +
      "the target language has one (tú / tu / du / etc).\n" +
      "- Return ONLY the translated text. No quotes, no preamble.";

  const response = await fetch(DEEPSEEK_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: DEEPSEEK_MODEL,
      messages: [
        {role: "system", content: systemPrompt},
        {role: "user", content: text},
      ],
      temperature: 0.3,
      max_tokens: 1500,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`DeepSeek translate ${response.status}: ${body}`);
  }
  const json = await response.json();
  const out = json?.choices?.[0]?.message?.content;
  if (!out) throw new Error("DeepSeek returned empty translation");
  return out.trim();
}

module.exports = {
  translateField,
  translateTemplate,
  normalizeLocale,
  isRtl,
  LANGUAGE_NAMES,
  SOURCE_LOCALE,
};
