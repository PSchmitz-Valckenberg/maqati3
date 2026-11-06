import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import ReviewEditor from './ReviewEditor';

// For the admins only; never in a search index.
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'admin.review' });
  return { title: t('title'), robots: { index: false, follow: false } };
}

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ locale: string; entryId: string }>;
}) {
  const { locale, entryId } = await params;
  setRequestLocale(locale);

  return (
    <main className="mx-auto max-w-4xl space-y-6 px-4 py-10">
      <ReviewEditor entryId={decodeURIComponent(entryId)} />
    </main>
  );
}
