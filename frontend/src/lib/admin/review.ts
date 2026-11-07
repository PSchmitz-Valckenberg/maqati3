/**
 * The review editor's logic, without any of its UI: who may edit, which moves the page
 * offers, how rows line up with the player.
 *
 * Like `logic.ts`, this only decides what the page offers. The server enforces every rule
 * (backend/src/maqati3/review.py): rows are edited and never added, removed or moved; a
 * language is edited only by the person who took it; and every change is logged.
 */
import type { Cue } from '@/lib/cues';

export type Lang = 'ar' | 'en' | 'de';

export type ReviewState =
  | 'not_started'
  | 'draft_ready'
  | 'in_progress'
  | 'awaiting_review'
  | 'needs_fixes'
  | 'approved';

export type LanguageInfo = { state: ReviewState; assignee: string | null };
export type Languages = Partial<Record<Lang, LanguageInfo>>;

/** What `/api/v1/admin/entries/{id}/review` says about one moment. */
export type ReviewRow = {
  idx: number;
  t_start_ms: number;
  t_end_ms: number | null;
  texts: Partial<Record<Lang, string>>;
};

export type MetadataState = 'none' | 'draft' | 'confirmed';

/** Title, question and keywords of an entry. `draft` means a model wrote it and nobody
 * has read it; `confirmed` means a person saved it. */
export type Metadata = {
  title: string;
  question: string;
  keywords: string[];
  state: MetadataState;
};

export type Review = {
  entry_id: string;
  rows: ReviewRow[];
  languages: Languages;
  metadata: Metadata | null;
};

/** Whether to offer the metadata draft. The server refuses without a model, before the
 * Arabic is approved, and over anything already there; a button that can only fail is
 * worse than none. */
export function canDraftMetadata({
  available,
  arabicApproved,
  state,
}: {
  available: boolean;
  arabicApproved: boolean;
  state: MetadataState;
}): boolean {
  return available && arabicApproved && state === 'none';
}

/** Keywords as a person types them, separated by commas: lowercase, no empties, no
 * repeats. The server tidies them again; this only shows what will be saved. */
export function keywordsFromText(text: string): string[] {
  const words: string[] = [];
  for (const part of text.split(',')) {
    const word = part.trim().toLowerCase();
    if (word !== '' && !words.includes(word)) words.push(word);
  }
  return words;
}

export type MoveOption = { to: ReviewState; key: 'take' | 'handOn' | 'approve' | 'sendBack' };

const ORDER: Lang[] = ['ar', 'en', 'de'];

/** Text is editable only while I am the one working on that language. */
export function canEdit(info: LanguageInfo | undefined, me: string): boolean {
  return info !== undefined && info.state === 'in_progress' && info.assignee === me;
}

/** The steps the page offers for one language. A subset of the server's state machine:
 * a draft is made by a worker and never by a click, and a translation is not worked on
 * before the Arabic is approved. The server refuses what is left out in any case. */
export function availableMoves(lang: string, languages: Languages, me: string): MoveOption[] {
  const info = languages[lang as Lang];
  if (info === undefined) return [];
  if (lang !== 'ar' && languages.ar?.state !== 'approved') return [];
  switch (info.state) {
    case 'draft_ready':
    case 'needs_fixes':
      return [{ to: 'in_progress', key: 'take' }];
    case 'in_progress':
      return info.assignee === me ? [{ to: 'awaiting_review', key: 'handOn' }] : [];
    case 'awaiting_review':
      return [
        { to: 'approved', key: 'approve' },
        { to: 'needs_fixes', key: 'sendBack' },
      ];
    default:
      return [];
  }
}

/** One cue per row, in order: the player follows the same rows the editor shows. */
export function rowCues(rows: readonly ReviewRow[]): Cue[] {
  return rows.map((row) => ({ idx: row.idx, startMs: row.t_start_ms, endMs: row.t_end_ms }));
}

/** Whether a draft differs from what is saved. Spaces at the ends are not a change: the
 * server trims them, and saving them would only write a log line for nothing. */
export function isDirty(saved: string, draft: string): boolean {
  return saved.trim() !== draft.trim();
}

/** Arabic first, then the other languages in a fixed order, only those that exist. */
export function languageOrder(languages: Languages): Lang[] {
  return ORDER.filter((lang) => languages[lang] !== undefined);
}
