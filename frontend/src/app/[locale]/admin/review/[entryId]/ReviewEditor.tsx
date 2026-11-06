'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import {
  AdminError,
  fetchMe,
  fetchReview,
  mediaUrl,
  moveLanguage,
  requestTranslation,
  saveRow,
} from '@/lib/admin/api';
import { canTranslate, errorKey } from '@/lib/admin/logic';
import {
  availableMoves,
  canEdit,
  isDirty,
  languageOrder,
  rowCues,
  type Lang,
  type Review,
  type ReviewRow,
} from '@/lib/admin/review';
import { findActiveCue } from '@/lib/cues';
import { formatDuration } from '@/lib/uploads/batch';

const LANGUAGE_NAMES: Record<Lang, string> = { ar: 'العربية', en: 'English', de: 'Deutsch' };
const BUTTON =
  'rounded-md px-3 py-1.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50';
const PRIMARY = `${BUTTON} bg-emerald-700 text-white`;
const SECONDARY = `${BUTTON} border border-neutral-400 bg-transparent`;

function subscribeToLocation(onChange: () => void): () => void {
  window.addEventListener('popstate', onChange);
  return () => window.removeEventListener('popstate', onChange);
}

/** The upload's file is named in the address (`?m=<sha256>`); anything else is ignored. */
function mediaOf(search: string): string | null {
  const value = new URLSearchParams(search).get('m');
  return value !== null && /^[0-9a-f]{64}$/.test(value) ? value : null;
}

function codeOf(error: unknown): string {
  return error instanceof AdminError ? error.code : 'network';
}

export default function ReviewEditor({ entryId }: { entryId: string }) {
  const t = useTranslations('admin.review');
  const te = useTranslations('admin.error');
  const locale = useLocale();
  const [review, setReview] = useState<Review | null>(null);
  const [me, setMe] = useState<string | null>(null);
  const [translation, setTranslation] = useState(false);
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTimes, setShowTimes] = useState(false);
  const [active, setActive] = useState(-1);
  const [busy, setBusy] = useState(false);
  const player = useRef<HTMLVideoElement>(null);
  const search = useSyncExternalStore(
    subscribeToLocation,
    () => window.location.search,
    () => '',
  );
  const sha256 = mediaOf(search);

  const reload = useCallback(async () => {
    try {
      setReview(await fetchReview(entryId));
    } catch (caught) {
      setError(codeOf(caught));
    }
  }, [entryId]);

  useEffect(() => {
    Promise.all([fetchReview(entryId), fetchMe()])
      .then(([loaded, who]) => {
        setReview(loaded);
        setMe(who.email);
        setTranslation(who.translation);
      })
      .catch((caught) => setError(codeOf(caught)));
  }, [entryId]);

  // While drafts are on their way, look again every few seconds: the worker is another process.
  useEffect(() => {
    if (!queued) return;
    const timer = setInterval(() => void reload(), 5000);
    return () => clearInterval(timer);
  }, [queued, reload]);

  async function requestDrafts() {
    setBusy(true);
    setError(null);
    try {
      await requestTranslation(entryId);
      setQueued(true);
    } catch (caught) {
      setError(codeOf(caught));
    }
    await reload();
    setBusy(false);
  }

  const cues = useMemo(() => rowCues(review?.rows ?? []), [review]);

  function seek(row: ReviewRow) {
    const video = player.current;
    if (video === null) return;
    video.currentTime = row.t_start_ms / 1000;
    void video.play().catch(() => undefined);
  }

  async function move(lang: Lang, to: Parameters<typeof moveLanguage>[2]) {
    if (to === 'approved' && !window.confirm(t('approveConfirm'))) return;
    setBusy(true);
    setError(null);
    try {
      await moveLanguage(entryId, lang, to);
    } catch (caught) {
      setError(codeOf(caught));
    }
    await reload();
    setBusy(false);
  }

  async function save(row: ReviewRow, lang: Lang, text: string): Promise<boolean> {
    setError(null);
    try {
      await saveRow(entryId, row.idx, lang, text);
    } catch (caught) {
      const code = codeOf(caught);
      setError(code);
      if (code !== 'empty_text' && code !== 'network') await reload();
      return false;
    }
    setReview((current) =>
      current === null
        ? current
        : {
            ...current,
            rows: current.rows.map((r) =>
              r.idx === row.idx ? { ...r, texts: { ...r.texts, [lang]: text.trim() } } : r,
            ),
          },
    );
    return true;
  }

  const back = `/${locale}/admin`;
  if (review === null || me === null) {
    return (
      <p>
        {error !== null ? te(errorKey(error)) : t('loading')}{' '}
        <a className="underline" href={back}>
          {t('back')}
        </a>
      </p>
    );
  }

  const order = languageOrder(review.languages);
  const hasPlayer = sha256 !== null;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <a className="text-sm underline" href={back}>
          {t('back')}
        </a>
        <h1 className="text-2xl font-semibold">
          {t('title')} · <bdi>{review.entry_id}</bdi>
        </h1>
        <p className="text-neutral-600 dark:text-neutral-400">{t('hint')}</p>
      </header>

      {error !== null && (
        <p role="alert" className="rounded-md border border-red-500 p-3 text-red-700 dark:text-red-300">
          {te(errorKey(error))}
        </p>
      )}

      {hasPlayer && (
        <div className="sticky top-0 z-10 bg-white pb-2 dark:bg-neutral-950">
          <video
            ref={player}
            controls
            playsInline
            preload="metadata"
            src={mediaUrl(sha256)}
            className="max-h-60 w-full rounded-md bg-black"
            onTimeUpdate={(event) =>
              setActive(findActiveCue(cues, event.currentTarget.currentTime * 1000))
            }
          />
        </div>
      )}

      <section className="space-y-3">
        {order.map((lang) => {
          const info = review.languages[lang];
          if (info === undefined) return null;
          const moves = availableMoves(lang, review.languages, me);
          return (
            <div key={lang} className="flex flex-wrap items-center gap-3 rounded-md border border-neutral-300 p-3 dark:border-neutral-700">
              <strong dir="auto">{LANGUAGE_NAMES[lang]}</strong>
              <span>{t(`state.${info.state}`)}</span>
              {info.state === 'in_progress' && info.assignee !== null && (
                <span className="text-sm text-neutral-600 dark:text-neutral-400">
                  {info.assignee === me ? t('mine') : t('takenBy', { name: info.assignee })}
                </span>
              )}
              {lang !== 'ar' &&
                review.languages.ar?.state !== 'approved' &&
                info.state === 'draft_ready' && (
                  <span className="text-sm text-neutral-600 dark:text-neutral-400">
                    {t('waitingForArabic')}
                  </span>
                )}
              <span className="ms-auto flex gap-2">
                {moves.map((option) => (
                  <button
                    key={option.to}
                    type="button"
                    disabled={busy}
                    className={option.key === 'sendBack' ? SECONDARY : PRIMARY}
                    onClick={() => void move(lang, option.to)}
                  >
                    {t(`move.${option.key}`)}
                  </button>
                ))}
              </span>
            </div>
          );
        })}
      </section>

      {canTranslate({
        translation,
        entryId: review.entry_id,
        transcript: 'ready',
        translations:
          review.languages.en?.state === 'not_started' &&
          review.languages.de?.state === 'not_started'
            ? 'none'
            : 'ready',
        arabicApproved: review.languages.ar?.state === 'approved',
      }) && (
        <button type="button" className={PRIMARY} disabled={busy} onClick={() => void requestDrafts()}>
          {t('requestDrafts')}
        </button>
      )}
      {queued &&
        (review.languages.en?.state === 'not_started' ||
          review.languages.de?.state === 'not_started') && (
          <p className="text-sm text-neutral-600 dark:text-neutral-400">{t('draftsQueued')}</p>
        )}

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={showTimes} onChange={(e) => setShowTimes(e.target.checked)} />
        {t('times')}
      </label>

      <ol className="space-y-3">
        {review.rows.map((row) => (
          <li
            key={row.idx}
            aria-label={t('rowLabel', { n: row.idx + 1 })}
            aria-current={active === row.idx ? 'true' : undefined}
            className={`space-y-2 rounded-md border p-3 ${
              active === row.idx
                ? 'border-emerald-600 bg-emerald-50 dark:bg-emerald-950'
                : 'border-neutral-300 dark:border-neutral-700'
            }`}
          >
            {hasPlayer && (
              <button
                type="button"
                className="text-sm underline"
                onClick={() => seek(row)}
                aria-label={t('rowLabel', { n: row.idx + 1 })}
              >
                {showTimes ? <bdi>{formatDuration(row.t_start_ms)}</bdi> : '▶'}
              </button>
            )}
            {!hasPlayer && showTimes && <bdi className="text-sm">{formatDuration(row.t_start_ms)}</bdi>}
            {order.map((lang) => {
              const saved = row.texts[lang];
              if (saved === undefined) return null;
              return (
                <RowText
                  // A new saved text starts a new draft: the box never shows stale words.
                  key={`${lang}:${saved}`}
                  lang={lang}
                  saved={saved}
                  editable={canEdit(review.languages[lang], me)}
                  // A click on text that is not yet mine takes the language, if it can be taken.
                  onTake={
                    availableMoves(lang, review.languages, me).some((m) => m.key === 'take')
                      ? () => move(lang, 'in_progress')
                      : undefined
                  }
                  onSave={(text) => save(row, lang, text)}
                />
              );
            })}
          </li>
        ))}
      </ol>
    </div>
  );
}

function RowText({
  lang,
  saved,
  editable,
  onTake,
  onSave,
}: {
  lang: Lang;
  saved: string;
  editable: boolean;
  onTake?: () => Promise<void>;
  onSave: (text: string) => Promise<boolean>;
}) {
  const t = useTranslations('admin.review');
  const [draft, setDraft] = useState(saved);
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [clicked, setClicked] = useState(false);
  const dir = lang === 'ar' ? 'rtl' : 'ltr';

  if (!editable) {
    return (
      <p
        dir={dir}
        lang={lang}
        className={`whitespace-pre-wrap ${onTake ? 'cursor-text rounded hover:bg-neutral-800/40' : ''}`}
        title={onTake ? t('readOnly') : undefined}
        onClick={
          onTake
            ? () => {
                setClicked(true);
                void onTake();
              }
            : undefined
        }
      >
        {saved}
      </p>
    );
  }
  return (
    <div className="space-y-1">
      <textarea
        dir={dir}
        lang={lang}
        value={draft}
        autoFocus={clicked}
        rows={2}
        aria-label={LANGUAGE_NAMES[lang]}
        className="w-full rounded-md border border-neutral-300 bg-transparent px-3 py-2 dark:border-neutral-700"
        onChange={(event) => {
          setDraft(event.target.value);
          setStatus('idle');
        }}
        onBlur={async () => {
          if (!isDirty(saved, draft)) return;
          setStatus('saving');
          const ok = await onSave(draft);
          setStatus(ok ? 'saved' : 'idle');
          if (!ok) setDraft(saved);
        }}
      />
      <p className="text-xs text-neutral-600 dark:text-neutral-400" aria-live="polite">
        {status === 'saving' ? t('saving') : status === 'saved' ? t('saved') : isDirty(saved, draft) ? t('unsaved') : ''}
      </p>
    </div>
  );
}
