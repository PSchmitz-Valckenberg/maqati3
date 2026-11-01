/**
 * The admin dashboard's logic, without any of its UI: how uploads are grouped, what a
 * sign-in came back with, which texts the server's error codes map to.
 *
 * The server enforces every rule that matters (backend/src/maqati3/api/admin.py); the
 * checks here only decide what the page offers and says.
 */

export type Scholar = { id: string; name_ar: string; name_en: string };

/** How an entry's transcription is going, as the server reads it off the queue and the
 * Arabic review state. `ready` means a transcript exists, whoever wrote it. */
export type TranscriptState = 'none' | 'queued' | 'running' | 'failed' | 'ready';

/** What `/api/v1/admin/submissions` says about one upload. */
export type Item = {
  sha256: string;
  original_name: string;
  duration_ms: number;
  received_at: string;
  contributor: string | null;
  /** Matches the contributor heard and kept the upload despite, in words. */
  kept_despite: string[];
  status: 'waiting' | 'registered';
  entry: { entry_id: string; scholar: Scholar } | null;
  registered_by: string | null;
  transcript: TranscriptState;
  /** Why the last run failed, as the queue recorded it. */
  transcript_error: string | null;
  /** How the English and German drafts are going, in the same five words. */
  translations: TranscriptState;
  /** Why the last draft run failed -- its own reason, not the transcription's. */
  translations_error: string | null;
};

export function groupItems(items: Item[]): { waiting: Item[]; registered: Item[] } {
  return {
    waiting: items.filter((i) => i.status === 'waiting'),
    registered: items.filter((i) => i.status === 'registered'),
  };
}

export type LoginResult = 'denied' | 'failed';

/** What the sign-in came back with, from the page's query string. Only the two values
 * the server sends are accepted, so the page never shows text taken from the URL. */
export function loginResult(search: string): LoginResult | null {
  const value = new URLSearchParams(search).get('login');
  return value === 'denied' || value === 'failed' ? value : null;
}

/** Where the dashboard sends the browser to sign in, asking to come back to itself. */
export function loginUrl(locale: string): string {
  return `/api/v1/admin/auth/login?return=${encodeURIComponent(`/${locale}/admin`)}`;
}

/** Registering needs a scholar, and only one request at a time. */
export function canRegister(scholarId: string, busy: boolean): boolean {
  return !busy && scholarId.trim() !== '';
}

/** Whether to offer the transcription button at all.
 *
 * The server refuses with 503 when no provider is configured, and this keeps the page
 * from showing a button that can only fail. `entryId` is null until an admin has
 * registered the upload: there is nothing to transcribe before there is an entry. */
export function canTranscribe({
  transcription,
  entryId,
  transcript,
}: {
  transcription: boolean;
  entryId: string | null;
  transcript: TranscriptState;
}): boolean {
  // `queued`, `running` and `ready` all answer 409 on the server. A run that failed
  // left nothing behind, so that one may be asked for again.
  return (
    transcription &&
    entryId !== null &&
    (transcript === 'none' || transcript === 'failed')
  );
}

/** Whether to offer the draft translations at all.
 *
 * There is nothing to translate until the Arabic transcript exists, so the button
 * waits for it: the server answers 409 otherwise, and a button that can only fail is
 * worse than none. A run that failed left nothing behind and may be asked for again. */
export function canTranslate({
  translation,
  entryId,
  transcript,
  translations,
}: {
  translation: boolean;
  entryId: string | null;
  transcript: TranscriptState;
  translations: TranscriptState;
}): boolean {
  return (
    translation &&
    entryId !== null &&
    transcript === 'ready' &&
    (translations === 'none' || translations === 'failed')
  );
}

const ERROR_KEYS: Record<string, string> = {
  not_waiting: 'notWaiting',
  unknown_scholar: 'unknownScholar',
  scholar_exists: 'scholarExists',
  admin_login_required: 'signedOut',
  transcription_not_configured: 'transcriptionNotConfigured',
  unknown_entry: 'unknownEntry',
  already_transcribed: 'alreadyTranscribed',
  already_queued: 'alreadyQueued',
  daily_limit_reached: 'dailyLimitReached',
  translation_not_configured: 'translationNotConfigured',
  nothing_to_translate: 'nothingToTranslate',
  already_translated: 'alreadyTranslated',
  network: 'network',
};

/** The text key for a server error code. Anything unknown is the general message: a raw
 * code is never shown to a person. */
export function errorKey(code: string): string {
  return ERROR_KEYS[code] ?? 'generic';
}

export function scholarLabel(scholar: Scholar, locale: string): string {
  return locale === 'ar' ? scholar.name_ar : scholar.name_en;
}

/** A first guess at a scholar's id from the Latin name: lowercase, plain letters,
 * hyphens. Empty when nothing usable is left. The id is the front of every entry id. */
export function slugFrom(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
