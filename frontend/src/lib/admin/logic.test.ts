import { describe, expect, it } from 'vitest';
import ar from '../../../messages/ar.json';
import de from '../../../messages/de.json';
import en from '../../../messages/en.json';
import {
  canRegister,
  canTranscribe,
  errorKey,
  groupItems,
  loginResult,
  loginUrl,
  scholarLabel,
  slugFrom,
  type Item,
} from './logic';

function item(overrides: Partial<Item> = {}): Item {
  return {
    sha256: 'aaa',
    original_name: 'clip.mp4',
    duration_ms: 80_333,
    received_at: '2026-10-27T14:00:00Z',
    contributor: 'Abdullah',
    kept_despite: [],
    status: 'waiting',
    entry: null,
    registered_by: null,
    ...overrides,
  };
}

describe('groupItems', () => {
  it('splits what waits from what is registered and keeps the order it was given', () => {
    const items = [
      item({ sha256: 'w1' }),
      item({ sha256: 'r1', status: 'registered' }),
      item({ sha256: 'w2' }),
    ];
    const { waiting, registered } = groupItems(items);
    expect(waiting.map((i) => i.sha256)).toEqual(['w1', 'w2']);
    expect(registered.map((i) => i.sha256)).toEqual(['r1']);
  });
});

describe('loginResult', () => {
  it('reads what the sign-in came back with', () => {
    expect(loginResult('?login=denied')).toBe('denied');
    expect(loginResult('?login=failed')).toBe('failed');
  });

  it('ignores anything else, so the page cannot be made to show arbitrary text', () => {
    expect(loginResult('')).toBeNull();
    expect(loginResult('?login=<script>')).toBeNull();
    expect(loginResult('?other=denied')).toBeNull();
  });
});

describe('loginUrl', () => {
  it('asks to come back to the dashboard in the same language', () => {
    expect(loginUrl('de')).toBe('/api/v1/admin/auth/login?return=%2Fde%2Fadmin');
    expect(loginUrl('ar')).toBe('/api/v1/admin/auth/login?return=%2Far%2Fadmin');
  });
});

describe('canRegister', () => {
  it('needs a scholar to be chosen', () => {
    expect(canRegister('', false)).toBe(false);
    expect(canRegister('   ', false)).toBe(false);
    expect(canRegister('ibn-baz', false)).toBe(true);
  });

  it('is off while the request is running, so one click cannot register twice', () => {
    expect(canRegister('ibn-baz', true)).toBe(false);
  });
});

describe('errorKey', () => {
  it('maps what the server says to a text the page has', () => {
    expect(errorKey('not_waiting')).toBe('notWaiting');
    expect(errorKey('unknown_scholar')).toBe('unknownScholar');
    expect(errorKey('scholar_exists')).toBe('scholarExists');
    expect(errorKey('admin_login_required')).toBe('signedOut');
    expect(errorKey('csrf_header_missing')).toBe('generic');
  });

  it('falls back to a general message and never shows a raw code', () => {
    expect(errorKey('something_new')).toBe('generic');
    expect(errorKey('network')).toBe('network');
  });
});

describe('scholarLabel', () => {
  const scholar = { id: 'ibn-baz', name_ar: 'ابن باز', name_en: 'Ibn Bāz' };

  it('shows the Arabic name on the Arabic page and the Latin one elsewhere', () => {
    expect(scholarLabel(scholar, 'ar')).toBe('ابن باز');
    expect(scholarLabel(scholar, 'en')).toBe('Ibn Bāz');
    expect(scholarLabel(scholar, 'de')).toBe('Ibn Bāz');
  });
});

describe('slugFrom', () => {
  it('turns a Latin name into the lowercase id an entry id can start with', () => {
    expect(slugFrom('Rabi al-Madkhali')).toBe('rabi-al-madkhali');
    expect(slugFrom('  Ibn  Bāz ')).toBe('ibn-baz');
    expect(slugFrom('Muhammad ibn Ṣāliḥ')).toBe('muhammad-ibn-salih');
  });

  it('is empty when nothing usable is left, so the field is never pre-filled with junk', () => {
    expect(slugFrom('')).toBe('');
    expect(slugFrom('!!!')).toBe('');
  });
});

describe('what the dashboard says when a transcription is refused', () => {
  /** The detail strings api/admin.py sends for the transcription route, each with the
   * message key the page looks them up under. */
  const refusals = [
    ['transcription_not_configured', 'transcriptionNotConfigured'],
    ['unknown_entry', 'unknownEntry'],
    ['already_transcribed', 'alreadyTranscribed'],
    ['already_queued', 'alreadyQueued'],
  ];

  it.each(refusals)('maps %s to its own message rather than the general one', (code, key) => {
    expect(errorKey(code)).toBe(key);
  });

  it.each(refusals)('has words for %s in all three languages', (_code, key) => {
    for (const messages of [en, de, ar]) {
      const text = (messages.admin.error as Record<string, string>)[key];
      expect(text ?? '').not.toBe('');
    }
  });

  it('offers the button only where the server said it can transcribe', () => {
    expect(canTranscribe({ transcription: false, entryId: 'ibn-baz-000042', busy: false })).toBe(
      false,
    );
    expect(canTranscribe({ transcription: true, entryId: null, busy: false })).toBe(false);
    expect(canTranscribe({ transcription: true, entryId: 'ibn-baz-000042', busy: true })).toBe(
      false,
    );
    expect(canTranscribe({ transcription: true, entryId: 'ibn-baz-000042', busy: false })).toBe(
      true,
    );
  });
});
