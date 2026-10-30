'use client';

import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { routing, type Locale } from '@/i18n/routing';

export const LANGUAGES: { code: Locale; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'ar', label: 'العربية' },
  { code: 'de', label: 'Deutsch' },
];

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

export default function LanguageSwitcher({ currentLocale }: { currentLocale: string }) {
  const pathname = usePathname() || '';
  const [hash, setHash] = useState('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setHash(window.location.hash);
      const onHashChange = () => setHash(window.location.hash);
      window.addEventListener('hashchange', onHashChange);
      return () => window.removeEventListener('hashchange', onHashChange);
    }
  }, []);

  return (
    <nav aria-label="Language switcher" className="flex items-center gap-1 text-sm">
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
