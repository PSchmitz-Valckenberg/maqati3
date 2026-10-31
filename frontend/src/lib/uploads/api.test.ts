import { describe, expect, it, vi } from 'vitest';
import ar from '../../../messages/ar.json';
import de from '../../../messages/de.json';
import en from '../../../messages/en.json';
import { mediaUrl, sendDecision, uploadFile } from './api';

describe('upload key transport security', () => {
  it('sends the upload key in X-Upload-Key header and not in the URL for uploadFile', async () => {
    let capturedUrl = '';
    let capturedMethod = '';
    const capturedHeaders: Record<string, string> = {};

    class MockXMLHttpRequest {
      upload = { onprogress: null };
      status = 200;
      responseText = JSON.stringify({ sha256: 'abc123', status: 'new', duplicate_of: null, candidates: [] });
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;

      open(method: string, url: string) {
        capturedMethod = method;
        capturedUrl = url;
      }

      setRequestHeader(name: string, value: string) {
        capturedHeaders[name] = value;
      }

      send() {
        if (this.onload) this.onload();
      }
    }

    const originalXHR = globalThis.XMLHttpRequest;
    globalThis.XMLHttpRequest = MockXMLHttpRequest as unknown as typeof XMLHttpRequest;

    const file = new File(['audio-content'], 'test.mp3', { type: 'audio/mp3' });
    const secretKey = 'secret-upload-key-xyz';

    try {
      await uploadFile(file, secretKey, () => {});
      expect(capturedMethod).toBe('POST');
      expect(capturedUrl).toBe('/api/v1/uploads');
      expect(capturedUrl).not.toContain(secretKey);
      expect(capturedHeaders['X-Upload-Key']).toBe(secretKey);
    } finally {
      globalThis.XMLHttpRequest = originalXHR;
    }
  });

  it('sends the upload key in X-Upload-Key header and not in the URL for sendDecision', async () => {
    const originalFetch = globalThis.fetch;
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;

    globalThis.fetch = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = String(input);
      capturedInit = init;
      return Promise.resolve(new Response(null, { status: 200 }));
    });

    const secretKey = 'secret-upload-key-xyz';
    const sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

    try {
      await sendDecision(sha256, { keep: true, contributor: 'Tester' }, secretKey);
      expect(capturedUrl).toBe(`/api/v1/uploads/${sha256}/decision`);
      expect(capturedUrl).not.toContain(secretKey);
      expect((capturedInit?.headers as Record<string, string>)['X-Upload-Key']).toBe(secretKey);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('puts the upload key only in the query for mediaUrl', () => {
    const secretKey = 'secret-upload-key-xyz';
    const previewId = 'preview-123';
    const url = mediaUrl(previewId, secretKey);

    expect(url).toBe('/api/v1/uploads/preview-123/media?k=secret-upload-key-xyz');
    expect(url).toContain(`?k=${secretKey}`);
  });
});

describe('what the page says when the server refuses', () => {
  /** The detail strings routes.py sends, each next to the message key the page looks up
   * for it. A refusal nobody has words for falls through to `error.other`, which shows
   * the contributor a bare code and tells them nothing about what to do. */
  const refusals = [
    { status: 429, detail: 'too_many_attempts' },
    { status: 401, detail: 'upload_key_required' },
    { status: 409, detail: 'not_awaiting_decision' },
  ];

  it.each(refusals)('turns $status into the code $detail', async ({ status, detail }) => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ detail }), { status })),
      );

    try {
      await expect(sendDecision('abc', { keep: false }, 'k')).rejects.toMatchObject({
        code: detail,
        status,
      });
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it.each(refusals)('has words for $detail in all three languages', ({ detail }) => {
    for (const messages of [en, de, ar]) {
      const text = (messages.upload.error as Record<string, string>)[detail];
      expect(text ?? '').not.toBe('');
    }
  });
});
