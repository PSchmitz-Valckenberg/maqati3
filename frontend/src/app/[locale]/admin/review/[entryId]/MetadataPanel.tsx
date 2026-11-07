'use client';

import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { canDraftMetadata, keywordsFromText, type Metadata } from '@/lib/admin/review';

const PRIMARY =
  'rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50';
const FIELD =
  'w-full rounded-md border border-neutral-300 bg-transparent px-3 py-2 dark:border-neutral-700';

type Fields = { title: string; question: string; keywords: string[] };

/** An entry's title, the question that was asked and a few keywords, in English.
 *
 * A model drafts them from the approved Arabic; nothing here is trusted until a person
 * has read it and pressed save, which is what the server then marks `confirmed`. */
export default function MetadataPanel({
  metadata,
  available,
  arabicApproved,
  busy,
  onDraft,
  onSave,
}: {
  metadata: Metadata | null;
  available: boolean;
  arabicApproved: boolean;
  busy: boolean;
  onDraft: () => void;
  onSave: (fields: Fields) => Promise<boolean>;
}) {
  const t = useTranslations('admin.review.metadata');
  const state = metadata?.state ?? 'none';

  return (
    <section className="space-y-3 rounded-md border border-neutral-300 p-3 dark:border-neutral-700">
      <h2 className="font-semibold">{t('title')}</h2>
      <p className="text-sm text-neutral-600 dark:text-neutral-400">
        {state === 'none'
          ? t('stateNone')
          : state === 'draft'
            ? t('stateDraft')
            : t('stateConfirmed')}
      </p>
      {canDraftMetadata({ available, arabicApproved, state }) && (
        <button type="button" className={PRIMARY} disabled={busy} onClick={onDraft}>
          {busy ? t('drafting') : t('draft')}
        </button>
      )}
      {available && !arabicApproved && state === 'none' && (
        <p className="text-sm text-neutral-600 dark:text-neutral-400">{t('waitingForArabic')}</p>
      )}
      {metadata !== null && state !== 'none' && (
        // A new saved text starts a new form: the boxes never show stale words.
        <MetadataForm
          key={`${metadata.title}|${metadata.question}|${metadata.keywords.join(',')}|${state}`}
          metadata={metadata}
          busy={busy}
          onSave={onSave}
        />
      )}
    </section>
  );
}

function MetadataForm({
  metadata,
  busy,
  onSave,
}: {
  metadata: Metadata;
  busy: boolean;
  onSave: (fields: Fields) => Promise<boolean>;
}) {
  const t = useTranslations('admin.review.metadata');
  const [title, setTitle] = useState(metadata.title);
  const [question, setQuestion] = useState(metadata.question);
  const [keywords, setKeywords] = useState(metadata.keywords.join(', '));
  const [saved, setSaved] = useState(false);

  function edit(set: (value: string) => void) {
    return (value: string) => {
      set(value);
      setSaved(false);
    };
  }

  return (
    <form
      className="space-y-2"
      onSubmit={async (event) => {
        event.preventDefault();
        setSaved(await onSave({ title, question, keywords: keywordsFromText(keywords) }));
      }}
    >
      <label className="block space-y-1 text-sm">
        {t('titleLabel')}
        <input
          className={FIELD}
          dir="auto"
          value={title}
          onChange={(e) => edit(setTitle)(e.target.value)}
        />
      </label>
      <label className="block space-y-1 text-sm">
        {t('questionLabel')}
        <textarea
          className={FIELD}
          dir="auto"
          rows={2}
          value={question}
          onChange={(e) => edit(setQuestion)(e.target.value)}
        />
      </label>
      <label className="block space-y-1 text-sm">
        {t('keywordsLabel')}
        <input
          className={FIELD}
          dir="auto"
          value={keywords}
          onChange={(e) => edit(setKeywords)(e.target.value)}
        />
      </label>
      <button type="submit" className={PRIMARY} disabled={busy || title.trim() === ''}>
        {t('save')}
      </button>
      {saved && <span className="ms-3 text-sm">{t('saved')}</span>}
    </form>
  );
}
