import { sanitizeCallbackUrl } from '@/lib/safe-redirect';

describe('sanitizeCallbackUrl', () => {
  it('keeps a normal root-relative path', () => {
    expect(sanitizeCallbackUrl('/upload')).toBe('/upload');
    expect(sanitizeCallbackUrl('/explore/abc?tab=1#top')).toBe('/explore/abc?tab=1#top');
  });

  it('falls back to /upload for null/empty', () => {
    expect(sanitizeCallbackUrl(null)).toBe('/upload');
    expect(sanitizeCallbackUrl(undefined)).toBe('/upload');
    expect(sanitizeCallbackUrl('')).toBe('/upload');
  });

  it('rejects absolute URLs with a scheme', () => {
    expect(sanitizeCallbackUrl('https://evil.example')).toBe('/upload');
    expect(sanitizeCallbackUrl('http://evil.example/path')).toBe('/upload');
    expect(sanitizeCallbackUrl('javascript:alert(1)')).toBe('/upload');
  });

  it('rejects protocol-relative //host', () => {
    expect(sanitizeCallbackUrl('//evil.example')).toBe('/upload');
    expect(sanitizeCallbackUrl('//evil.example/path')).toBe('/upload');
  });

  it('rejects backslash tricks browsers normalize to //', () => {
    expect(sanitizeCallbackUrl('/\\evil.example')).toBe('/upload');
    expect(sanitizeCallbackUrl('/\\/evil.example')).toBe('/upload');
    expect(sanitizeCallbackUrl('\\evil.example')).toBe('/upload');
  });

  it('rejects paths that do not start with a single slash', () => {
    expect(sanitizeCallbackUrl('upload')).toBe('/upload');
    expect(sanitizeCallbackUrl(' /upload')).toBe('/upload'); // leading space
  });

  it('honors a custom fallback', () => {
    expect(sanitizeCallbackUrl('https://evil.example', '/dashboard')).toBe('/dashboard');
  });
});
