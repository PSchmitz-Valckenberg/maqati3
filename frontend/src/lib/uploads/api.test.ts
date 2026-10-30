import { describe, expect, it, vi } from 'vitest';
import { mediaUrl, sendDecision, uploadFile } from './api';

describe('upload key transport (integrity)', () => {
  it('puts the key in X-Upload-Key header and never in the URL for uploadFile', async () => {
    let capturedUrl = '';
    const capturedHeaders: Record<string, string> = {};

    const mockXHR = {
      open: vi.fn((_method: string, url: string) => {
        capturedUrl = url;
      }),
      setRequestHeader: vi.fn((name: string, value: string) => {
        capturedHeaders[name] = value;
      }),
      upload: { onprogress: null },
      send: vi.fn(function (this: any) {
        this.status = 200;
        this.responseText = JSON.stringify({
          sha256: 'abc123sha',
          status: 'new',
          duplicate_of: null,
          candidates: [],
        });
        if (this.onload) this.onload();
      }),
      onload: null,
      onerror: null,
      status: 200,
      responseText: '',
    };

    const originalXHR = globalThis.XMLHttpRequest;
    globalThis.XMLHttpRequest = vi.fn(() => mockXHR as any) as any;

    try {
      const file = new File(['dummy-content'], 'test.mp4', { type: 'video/mp4' });
      const result = await uploadFile(file, 'secret-key-123', () => {});

      expect(result.sha256).toBe('abc123sha');
      expect(capturedUrl).toBe('/api/v1/uploads');
      expect(capturedUrl).not.toContain('secret-key-123');
      expect(capturedUrl).not.toContain('?k=');
      expect(capturedHeaders['X-Upload-Key']).toBe('secret-key-123');
    } finally {
      globalThis.XMLHttpRequest = originalXHR;
    }
  });

  it('puts the key in X-Upload-Key header and never in the URL for sendDecision', async () => {
    let capturedUrl = '';
    let capturedHeaders: Record<string, string> = {};

    const mockFetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = String(input);
      capturedHeaders = (init?.headers as Record<string, string>) || {};
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    const originalFetch = globalThis.fetch;
    globalThis.fetch = mockFetch;

    try {
      await sendDecision(
        'sha256hash',
        { action: 'send', sender: 'Abdullah', choice: null },
        'secret-key-123',
      );

      expect(capturedUrl).toBe('/api/v1/uploads/sha256hash/decision');
      expect(capturedUrl).not.toContain('secret-key-123');
      expect(capturedUrl).not.toContain('?k=');
      expect(capturedHeaders['X-Upload-Key']).toBe('secret-key-123');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('puts the key in the query string exclusively for mediaUrl', () => {
    const url = mediaUrl('preview-999', 'my-secret+key');
    expect(url).toBe('/api/v1/uploads/preview-999/media?k=my-secret%2Bkey');
    expect(url).toContain('?k=my-secret%2Bkey');
  });
});
