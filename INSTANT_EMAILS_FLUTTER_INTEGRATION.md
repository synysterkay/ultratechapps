# Instant Emails — Flutter Integration Guide

Two Supabase Edge Functions on the marketing-tool fire instant emails when
high-conversion Thesis Generator events happen. The Flutter app needs to call
each one with a single HTTP POST right after writing the corresponding state
to Firestore.

| Event | Edge Function URL | When to fire |
|---|---|---|
| First thesis completion | `https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/thesis-complete-email` | Right after writing `theses/{id}.status = 'completed'` |
| Free quota hit (paywall shown) | `https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/free-quota-hit-email` | Right after writing `users/{uid}.usage.freeChapterUsed = true` |

Both:
- Authenticate via `Authorization: Bearer <SUPABASE_ANON_KEY>` (same key already used by other Supabase calls in the app)
- Are idempotent — duplicate POSTs return `{ ok: true, duplicate: true }` instead of double-sending
- Return JSON with status code 200 on success, 400 on bad input, 500 on send failure
- Are fully localized — pass the user's chosen `language` (`en`, `ar`, `es`, `fr`, `hi`, `zh`, etc.) and the email body will be in that language

## Dart implementation

Add this single helper to `lib/services/instant_email_service.dart`:

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class InstantEmailService {
  static const String _baseUrl =
      'https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1';
  static const String _anonKey =
      'eyJhbGciOi...'; // your existing Supabase anon key

  static Future<void> _fire(String endpoint, Map<String, dynamic> body) async {
    // Best-effort fire-and-forget. Failure is non-fatal — the batch
    // sender will catch the user on the next cron if this misses.
    try {
      await http.post(
        Uri.parse('$_baseUrl/$endpoint'),
        headers: {
          'Authorization': 'Bearer $_anonKey',
          'Content-Type': 'application/json',
        },
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 5));
    } catch (_) {
      // swallow — instant email is an enhancement, not a correctness path
    }
  }

  /// Call right after writing `theses/{thesisId}.status = 'completed'`.
  static Future<void> thesisCompleted({
    required String uid,
    required String email,
    required String thesisId,
    String language = 'en',
    String firstName = 'there',
    String workType = 'thesis',
    String topic = 'your work',
  }) async {
    await _fire('thesis-complete-email', {
      'uid': uid,
      'email': email,
      'thesis_id': thesisId,
      'language': language,
      'first_name': firstName,
      'work_type': workType,
      'topic': topic,
    });
  }

  /// Call right after writing `users/{uid}.usage.freeChapterUsed = true`
  /// (when the paywall first appears).
  static Future<void> freeQuotaHit({
    required String uid,
    required String email,
    String language = 'en',
    String firstName = 'there',
    String workType = 'thesis',
    String topic = 'your work',
  }) async {
    await _fire('free-quota-hit-email', {
      'uid': uid,
      'email': email,
      'language': language,
      'first_name': firstName,
      'work_type': workType,
      'topic': topic,
    });
  }
}
```

## Call sites

### 1. Background thesis generation completion

In `background_gen_service.dart` (or wherever the thesis status flips to
completed), add the call after the Firestore write:

```dart
await FirebaseFirestore.instance
    .collection('theses')
    .doc(thesisId)
    .update({'status': 'completed', /* ... */ });

// NEW — fire instant celebratory email (non-blocking)
InstantEmailService.thesisCompleted(
  uid: currentUser.uid,
  email: currentUser.email!,
  thesisId: thesisId,
  language: localeProvider.bcp47Tag,
  firstName: userDoc['displayName']?.split(' ').first ?? 'there',
  workType: planDoc['workType'] ?? 'thesis',
  topic: planDoc['topic'] ?? 'your work',
);
```

### 2. Free quota hit (paywall appears)

In `chapter_gate_service.dart` (or wherever `usage.freeChapterUsed` is set
to true), add the call after the Firestore write:

```dart
await FirebaseFirestore.instance
    .collection('users')
    .doc(uid)
    .set({
      'usage': {
        'freeChapterUsed': true,
        'freeChapterUsedAt': FieldValue.serverTimestamp(),
      },
    }, SetOptions(merge: true));

// NEW — fire instant upgrade-nudge email (non-blocking)
InstantEmailService.freeQuotaHit(
  uid: uid,
  email: currentUser.email!,
  language: localeProvider.bcp47Tag,
  firstName: userDoc['displayName']?.split(' ').first ?? 'there',
  workType: planDoc['workType'] ?? 'thesis',
  topic: planDoc['topic'] ?? 'your work',
);
```

## Behavior during rollout

| App version | What happens on event | Latency |
|---|---|---|
| Old (no call to InstantEmailService) | Batch sender picks up the user on the next 09:00 / 17:00 UTC cron | up to 12h |
| New (with the helper) | Edge Function fires the email within seconds; batch sender skips the user via the Supabase dedup table | 2-5s |

Mixed-version traffic is handled gracefully — neither version sends a
duplicate to the same user. The dedup is keyed by `(uid, event_kind)`
in `public.instant_emails_sent` and both the Edge Function and the
batch sender check the same table.

## What you'll see after shipping the app update

Within minutes of the user's action, an email lands in their inbox with:
- Subject like `🎓 You did it, Ana — export your thesis` (or localized)
- Tags `kind=thesis_complete` / `kind=free_quota_hit` in Resend dashboard
- UTM-tagged CTAs for click attribution back to app installs / subscriptions

Check the Supabase `instant_emails_sent` table to see real-time delivery:

```sql
select event_kind, language, count(*), max(sent_at)
from instant_emails_sent
where sent_at > now() - interval '1 day'
group by event_kind, language
order by count(*) desc;
```

## Rotating the anon key

The Supabase anon key embedded in the Dart code is the same one already
used everywhere in the app. If it gets rotated, both the existing
Supabase calls AND `InstantEmailService` need the new value — they
share the same key surface.
