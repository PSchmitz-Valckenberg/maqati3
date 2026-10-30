import { describe, expect, it } from 'vitest';
import { buildLocaleUrl, LANGUAGES } from './LanguageSwitcher';

describe('LanguageSwitcher buildLocaleUrl', () => {
  it('switches locale from /en/upload to /ar/upload', () => {
    expect(buildLocaleUrl('/en/upload', 'ar')).toBe('/ar/upload');
  });

  it('switches locale from /ar/admin to /de/admin', () => {
    expect(buildLocaleUrl('/ar/admin', 'de')).toBe('/de/admin');
  });

  it('preserves the #k= upload key fragment across language switches', () => {
    expect(buildLocaleUrl('/en/upload', 'ar', '#k=myUploadKey123')).toBe(
      '/ar/upload#k=myUploadKey123',
    );
    expect(buildLocaleUrl('/ar/upload', 'de', '#k=token%2B123')).toBe(
      '/de/upload#k=token%2B123',
    );
  });

  it('has native names for all 3 supported languages', () => {
    expect(LANGUAGES).toEqual([
      { code: 'en', label: 'English' },
      { code: 'ar', label: 'العربية' },
      { code: 'de', label: 'Deutsch' },
    ]);
  });
});
