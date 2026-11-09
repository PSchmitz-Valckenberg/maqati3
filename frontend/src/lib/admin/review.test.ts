import { describe, expect, it } from 'vitest';
import ar from '../../../messages/ar.json';
import de from '../../../messages/de.json';
import en from '../../../messages/en.json';
import { errorKey } from './logic';
import {
  availableMoves,
  canConfirmSecond,
  canDraftMetadata,
  canJudgeRows,
  SPAN_ROLES,
  canEdit,
  keywordsFromText,
  isDirty,
  languageOrder,
  rowCues,
  type Languages,
  type ReviewRow,
} from './review';

const ME = 'yusuf@example.org';
const OTHER = 'aisha@example.org';

function languages(overrides: Languages = {}): Languages {
  return {
    ar: { state: 'approved', assignee: null },
    en: { state: 'draft_ready', assignee: null },
    ...overrides,
  };
}

describe('who may edit', () => {
  it('only the person who has taken the language, and only while it is in progress', () => {
    expect(canEdit({ state: 'in_progress', assignee: ME }, ME)).toBe(true);
  });

  it.each(['draft_ready', 'awaiting_review', 'needs_fixes', 'approved', 'not_started'] as const)(
    'nobody edits a language that is %s',
    (state) => {
      expect(canEdit({ state, assignee: ME }, ME)).toBe(false);
    },
  );

  it('nobody edits a language someone else has taken', () => {
    expect(canEdit({ state: 'in_progress', assignee: OTHER }, ME)).toBe(false);
  });

  it('a language that is not there cannot be edited', () => {
    expect(canEdit(undefined, ME)).toBe(false);
  });
});

describe('which moves the page offers', () => {
  const moves = (lang: string, l: Languages) => availableMoves(lang, l, ME).map((m) => m.to);

  it('a draft can be taken', () => {
    expect(moves('en', languages())).toEqual(['in_progress']);
  });

  it('work that was sent back can be taken again', () => {
    expect(moves('ar', languages({ ar: { state: 'needs_fixes', assignee: OTHER } }))).toEqual([
      'in_progress',
    ]);
  });

  it('what I am working on can be handed on, and nothing else', () => {
    expect(moves('ar', languages({ ar: { state: 'in_progress', assignee: ME } }))).toEqual([
      'awaiting_review',
    ]);
  });

  it('what someone else is working on offers nothing', () => {
    expect(moves('ar', languages({ ar: { state: 'in_progress', assignee: OTHER } }))).toEqual([]);
  });

  it('what waits for review can be approved or sent back', () => {
    expect(
      moves('ar', languages({ ar: { state: 'awaiting_review', assignee: OTHER } })),
    ).toEqual(['approved', 'needs_fixes']);
  });

  it.each(['approved', 'not_started'] as const)('a language that is %s offers nothing', (state) => {
    expect(moves('ar', languages({ ar: { state, assignee: null } }))).toEqual([]);
  });

  it('a translation offers nothing while the Arabic is not approved', () => {
    expect(
      moves('en', languages({ ar: { state: 'awaiting_review', assignee: ME } })),
    ).toEqual([]);
  });

  it('a language that is not there offers nothing', () => {
    expect(moves('de', languages())).toEqual([]);
  });
});

describe('rows and text', () => {
  const rows: ReviewRow[] = [
    { idx: 0, t_start_ms: 0, t_end_ms: 2400, texts: { ar: 'أ', en: 'a' } },
    { idx: 1, t_start_ms: 2500, t_end_ms: null, texts: { ar: 'ب' } },
  ];

  it('rows become cues in the same order, one for one', () => {
    expect(rowCues(rows)).toEqual([
      { idx: 0, startMs: 0, endMs: 2400 },
      { idx: 1, startMs: 2500, endMs: null },
    ]);
  });

  it('a draft differs from the saved text only by more than whitespace at the ends', () => {
    expect(isDirty('هذا جائز.', 'هذا جائز.')).toBe(false);
    expect(isDirty('هذا جائز.', '  هذا جائز.\n')).toBe(false);
    expect(isDirty('هذا جائز.', 'هذا جائز جدا.')).toBe(true);
  });

  it('Arabic comes first, then the languages that have text', () => {
    expect(languageOrder(languages({ de: { state: 'draft_ready', assignee: null } }))).toEqual([
      'ar',
      'en',
      'de',
    ]);
    expect(languageOrder({ en: { state: 'draft_ready', assignee: null } })).toEqual(['en']);
  });
});

describe('what the server refuses with', () => {
  it.each([
    ['unknown_row', 'unknownRow'],
    ['not_in_progress', 'notInProgress'],
    ['claimed_by_other', 'claimedByOther'],
    ['empty_text', 'emptyText'],
    ['invalid_transition', 'invalidTransition'],
    ['review_not_available', 'reviewNotAvailable'],
  ])('%s is told in words in every language', (code, key) => {
    expect(errorKey(code)).toBe(key);
    for (const messages of [en, de, ar]) {
      const text = (messages.admin.error as Record<string, string>)[key];
      expect(text, `${key} missing`).toBeTruthy();
    }
  });

  it('every text of the review page exists in every language', () => {
    const keys = (m: typeof en) => Object.keys((m.admin as Record<string, unknown>).review as object).sort();
    expect(keys(de)).toEqual(keys(en));
    expect(keys(ar)).toEqual(keys(en));
  });
});

describe('metadata', () => {
  it('a draft is offered once the Arabic is approved and nothing exists yet', () => {
    expect(canDraftMetadata({ available: true, arabicApproved: true, state: 'none' })).toBe(true);
  });

  it.each([
    [{ available: false, arabicApproved: true, state: 'none' as const }],
    [{ available: true, arabicApproved: false, state: 'none' as const }],
    [{ available: true, arabicApproved: true, state: 'draft' as const }],
    [{ available: true, arabicApproved: true, state: 'confirmed' as const }],
  ])('no draft is offered when the server would refuse it: %j', (input) => {
    expect(canDraftMetadata(input)).toBe(false);
  });

  it('keywords are typed with commas and come out tidy', () => {
    expect(keywordsFromText(' Family, mother,, family ,KINDNESS ')).toEqual([
      'family',
      'mother',
      'kindness',
    ]);
    expect(keywordsFromText('')).toEqual([]);
  });

  it('the server refusals are told in words in every language', () => {
    for (const [code, key] of [
      ['already_drafted', 'alreadyDrafted'],
      ['metadata_failed', 'metadataFailed'],
      ['empty_title', 'emptyTitle'],
      ['metadata_not_configured', 'metadataNotConfigured'],
    ]) {
      expect(errorKey(code)).toBe(key);
      for (const m of [en, de, ar]) {
        expect((m.admin.error as Record<string, string>)[key]).toBeTruthy();
      }
    }
  });
});

describe('who speaks on a row (issue #26)', () => {
  const row = (span_role: ReviewRow['span_role'], citable = false): ReviewRow => ({
    idx: 0,
    t_start_ms: 0,
    t_end_ms: 1000,
    texts: { ar: 'أ' },
    span_role,
    citable,
  });

  it('offers exactly the five roles, the unclear one first', () => {
    expect(SPAN_ROLES).toEqual([
      'unclear',
      'scholar_own',
      'questioner',
      'quoted_other',
      'recited_text',
    ]);
  });

  it('roles are judged only by the person who has taken the Arabic', () => {
    expect(canJudgeRows({ ar: { state: 'in_progress', assignee: ME } }, ME)).toBe(true);
    expect(canJudgeRows({ ar: { state: 'in_progress', assignee: OTHER } }, ME)).toBe(false);
    expect(canJudgeRows({ ar: { state: 'approved', assignee: ME } }, ME)).toBe(false);
    expect(canJudgeRows({ en: { state: 'in_progress', assignee: ME } }, ME)).toBe(false);
  });

  it('a second can be confirmed once the speaker is known, and never before', () => {
    expect(canConfirmSecond(row('unclear'))).toBe(false);
    for (const role of ['scholar_own', 'questioner', 'quoted_other', 'recited_text'] as const) {
      expect(canConfirmSecond(row(role))).toBe(true);
    }
  });

  it('a confirmation that was made can always be taken back', () => {
    expect(canConfirmSecond(row('scholar_own', true))).toBe(true);
  });

  it('every role and the new refusal are told in words in every language', () => {
    expect(errorKey('role_not_set')).toBe('roleNotSet');
    for (const m of [en, de, ar]) {
      expect((m.admin.error as Record<string, string>).roleNotSet).toBeTruthy();
      const roles = (m.admin.review as unknown as { role: Record<string, string> }).role;
      for (const role of SPAN_ROLES) expect(roles[role], role).toBeTruthy();
    }
  });
});
