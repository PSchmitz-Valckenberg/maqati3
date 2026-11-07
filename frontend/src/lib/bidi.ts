/**
 * Telling the numbers in a text from the words around them.
 *
 * In an Arabic paragraph the browser's bidirectional algorithm can reorder a run of
 * digits and the punctuation next to it. For prose that is cosmetic. For a hadith number,
 * a year or a timecode it is a false statement: "1234" shown as "4321" cites another
 * hadith. So every such run is wrapped in `.bidi-isolate` where it is written into the
 * page, and `components/BidiText` is the one place that does it.
 */

export type Run = { text: string; number: boolean };

// Western, Arabic-Indic and Extended Arabic-Indic (Persian) digits.
const DIGIT = '[0-9\\u0660-\\u0669\\u06F0-\\u06F9]';
// A number is digits, and between digits the marks a figure is written with: a timecode
// (4:12), a decimal or thousands mark, a range (5-7). A mark must have a digit on both
// sides, so the full stop after "2026." or the dash in "5-" stay out of it.
const NUMBER = new RegExp(`${DIGIT}+(?:[:.,\\u066B\\u066C\\-/]${DIGIT}+)*`, 'gu');

/** Cuts a text into runs, in order, so that joining them gives the text back. A run
 * is either a number or the words between numbers; nothing is dropped or added. */
export function splitNumberRuns(text: string): Run[] {
  const runs: Run[] = [];
  let last = 0;
  for (const match of text.matchAll(NUMBER)) {
    const start = match.index;
    if (start > last) runs.push({ text: text.slice(last, start), number: false });
    runs.push({ text: match[0], number: true });
    last = start + match[0].length;
  }
  if (last < text.length) runs.push({ text: text.slice(last), number: false });
  return runs;
}
