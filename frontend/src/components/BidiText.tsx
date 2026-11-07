import { Fragment } from 'react';
// Relative, not "@/": the unit tests run without the framework's path aliases.
import { splitNumberRuns } from '../lib/bidi';

/** Text with every run of digits isolated from the right-to-left text around it.
 *
 * Use this wherever a transcript, a title or a question is written into the page: a
 * hadith number that renders reversed is a false claim about a source (issue #33).
 * It renders text, never markup, so a transcript cannot inject any. */
export default function BidiText({ text }: { text: string }) {
  return (
    <>
      {splitNumberRuns(text).map((run, i) =>
        run.number ? (
          <span key={i} className="bidi-isolate" dir="ltr">
            {run.text}
          </span>
        ) : (
          <Fragment key={i}>{run.text}</Fragment>
        ),
      )}
    </>
  );
}
