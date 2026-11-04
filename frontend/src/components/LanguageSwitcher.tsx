'use client';

import { usePathname } from 'next/navigation';
import { useSyncExternalStore } from 'react';
import { routing, type Locale } from '../i18n/routing';

export const LANGUAGES: { code: Locale; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'ar', label: 'العربية' },
  { code: 'de', label: 'Deutsch' },
];

export const NAV_LABELS: Record<string, string> = {
  en: 'Language switcher',
  de: 'Sprachauswahl',
  ar: 'تبديل اللغة',
};

function subscribeToHash(callback: () => void) {
  window.addEventListener('hashchange', callback);
  return () => window.removeEventListener('hashchange', callback);
}

function getHashSnapshot() {
  return typeof window !== 'undefined' ? window.location.hash : '';
}

function getHashServerSnapshot() {
  return '';
}

/**
 * Replace the locale prefix in a pathname while keeping the route and fragment intact.
 */
export function buildLocaleUrl(pathname: string, newLocale: Locale, hash: string = ''): string {
  const segments = pathname.split('/');
  if (segments.length > 1 && routing.locales.includes(segments[1] as Locale)) {
    segments[1] = newLocale;
  } else {
    segments.splice(1, 0, newLocale);
  }
  const cleanHash = hash ? (hash.startsWith('#') ? hash : `#${hash}`) : '';
  return segments.join('/') + cleanHash;
}

export default function LanguageSwitcher({
  currentLocale,
  label,
}: {
  currentLocale: string;
  label?: string;
}) {
  const pathname = usePathname() || '';
  const hash = useSyncExternalStore(subscribeToHash, getHashSnapshot, getHashServerSnapshot);
  const navAriaLabel = label || NAV_LABELS[currentLocale] || NAV_LABELS.en;

  return (
    <nav aria-label={navAriaLabel} className="flex items-center gap-1 text-sm">
      {LANGUAGES.map(({ code, label }) => {
        const isCurrent = code === currentLocale;
        const href = buildLocaleUrl(pathname, code, hash);
        return isCurrent ? (
          <span
            key={code}
            className="rounded px-2.5 py-1 font-medium bg-neutral-200/70 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100"
            aria-current="true"
          >
            {label}
          </span>
        ) : (
          <a
            key={code}
            href={href}
            className="rounded px-2.5 py-1 text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:text-neutral-200 dark:hover:bg-neutral-800/50 transition-colors"
          >
            {label}
          </a>
        );
      })}
    </nav>
  );
}
