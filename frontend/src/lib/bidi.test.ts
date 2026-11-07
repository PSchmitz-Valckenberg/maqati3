import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import BidiText from '@/components/BidiText';
import { splitNumberRuns } from './bidi';

const numbers = (text: string) => splitNumberRuns(text).filter((r) => r.number).map((r) => r.text);

describe('which parts of a text are numbers', () => {
  it('text with no digits is one plain run', () => {
    expect(splitNumberRuns('ما حكم هذا؟')).toEqual([{ text: 'ما حكم هذا؟', number: false }]);
  });

  it('empty text has no runs at all', () => {
    expect(splitNumberRuns('')).toEqual([]);
  });

  it('a hadith number is isolated from the Arabic around it', () => {
    expect(splitNumberRuns('حديث رقم 1234 في البخاري')).toEqual([
      { text: 'حديث رقم ', number: false },
      { text: '1234', number: true },
      { text: ' في البخاري', number: false },
    ]);
  });

  it('a year is a number', () => {
    expect(numbers('في سنة 1445 هـ')).toEqual(['1445']);
  });

  it.each(['4:12', '1:02:03', '252', '4.12', '5-7', '1,000'])(
    'a timecode, a range or a figure like %s stays one run',
    (figure) => {
      expect(numbers(`قال في ${figure} ثم`)).toEqual([figure]);
    },
  );

  it('Arabic-Indic and Persian digits are numbers too', () => {
    expect(numbers('الحديث ١٢٣ والآية ۴۵')).toEqual(['١٢٣', '۴۵']);
    expect(numbers('عند ٤:١٢')).toEqual(['٤:١٢']);
  });

  it('punctuation after a number is not part of it', () => {
    expect(numbers('في 2026.')).toEqual(['2026']);
    expect(numbers('حديث 12، ثم 13:')).toEqual(['12', '13']);
  });

  it('two numbers in a row are two runs when words separate them', () => {
    expect(numbers('بين 5 و 7')).toEqual(['5', '7']);
  });

  it.each([
    'حديث رقم 1234 في البخاري',
    '4:12 ثم 1:02:03.',
    'بلا أرقام',
    '٤:١٢،',
    '5-',
    '-5',
  ])('nothing is lost or added: %s', (text) => {
    expect(
      splitNumberRuns(text)
        .map((r) => r.text)
        .join(''),
    ).toBe(text);
  });
});

describe('the helper that makes the right thing the easy thing', () => {
  const html = (text: string) => renderToStaticMarkup(createElement(BidiText, { text }));

  it('wraps every number run in an isolated, left-to-right span', () => {
    expect(html('حديث رقم 1234 وسنة 1445')).toBe(
      'حديث رقم <span class="bidi-isolate" dir="ltr">1234</span> وسنة ' +
        '<span class="bidi-isolate" dir="ltr">1445</span>',
    );
  });

  it('leaves text without numbers untouched', () => {
    expect(html('ما حكم هذا؟')).toBe('ما حكم هذا؟');
  });

  it('escapes what it renders: a transcript is not markup', () => {
    expect(html('<b>5</b>')).toBe(
      '&lt;b&gt;<span class="bidi-isolate" dir="ltr">5</span>&lt;/b&gt;',
    );
  });
});
