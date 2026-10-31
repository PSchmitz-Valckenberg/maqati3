import { describe, expect, it, vi } from 'vitest';
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
      await sendDecision(sha256, { choice: 'new', sender: 'Tester' }, secretKey);
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
