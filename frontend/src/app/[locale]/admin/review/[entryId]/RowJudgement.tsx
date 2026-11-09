'use client';

import { useTranslations } from 'next-intl';
import { canConfirmSecond, SPAN_ROLES, type ReviewRow, type SpanRole } from '@/lib/admin/review';

/** Whose words a row holds, and whether its second has been confirmed (issue #26).
 *
 * Only a row of the scholar's own words with a confirmed second can ever be quoted, so
 * this is where that is decided, by a person, row by row. Everyone starts as unclear. */
export default function RowJudgement({
  row,
  editable,
  busy,
  onRole,
  onConfirm,
}: {
  row: ReviewRow;
  editable: boolean;
  busy: boolean;
  onRole: (role: SpanRole) => void;
  onConfirm: (confirmed: boolean) => void;
}) {
  const t = useTranslations('admin.review');

  if (!editable) {
    return (
      <p className="text-xs text-neutral-600 dark:text-neutral-400">
        {t(`role.${row.span_role}`)}
        {row.citable && <> · {t('secondConfirmed')}</>}
      </p>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm" title={t('secondHint')}>
      <label className="flex items-center gap-2">
        <span className="text-neutral-600 dark:text-neutral-400">{t('roleLabel')}</span>
        <select
          value={row.span_role}
          disabled={busy}
          className="rounded-md border border-neutral-300 bg-transparent px-2 py-1 dark:border-neutral-700"
          onChange={(event) => onRole(event.target.value as SpanRole)}
        >
          {SPAN_ROLES.map((role) => (
            <option key={role} value={role} className="text-black">
              {t(`role.${role}`)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={row.citable}
          disabled={busy || !canConfirmSecond(row)}
          onChange={(event) => onConfirm(event.target.checked)}
        />
        {t('secondConfirmed')}
      </label>
    </div>
  );
}
