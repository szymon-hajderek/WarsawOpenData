import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ageGroup, CITY_SHARING_KEY, logCityEvent, revokeCityConsent } from './cityEvents';

describe('city research submissions', () => {
  beforeEach(() => { localStorage.clear(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it.each([[null, null], [undefined, null], [10, '<18'], [17, '<18'], [18, '18-24'],
    [24, '18-24'], [25, '25-34'], [34, '25-34'], [35, '35-44'], [44, '35-44'],
    [45, '45-54'], [55, '55-64'], [65, '65+'], [100, '65+']])('buckets %s as %s', (age, expected) => {
    expect(ageGroup(age as number | null | undefined)).toBe(expected);
  });

  it('does not send anything without opt-in', async () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    await logCityEvent('search', {});
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('retries with the same event UUID and only the age bucket', async () => {
    localStorage.setItem(CITY_SHARING_KEY, 'true');
    localStorage.setItem('preferences', JSON.stringify({ base: { body: { age: 27 } } }));
    const fetcher = vi.fn().mockResolvedValueOnce({ ok: false, status: 503 }).mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetcher);
    await logCityEvent('search', { result_count: 0 });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[0][1].body).toBe(fetcher.mock.calls[1][1].body);
    const sent = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(sent.age_group).toBe('25-34'); expect(sent.age).toBeUndefined();
  });

  it('keeps an empty age unknown instead of the calorie fallback', async () => {
    localStorage.setItem(CITY_SHARING_KEY, 'true');
    const fetcher = vi.fn().mockResolvedValue({ ok: true }); vi.stubGlobal('fetch', fetcher);
    await logCityEvent('search', {});
    expect(JSON.parse(fetcher.mock.calls[0][1].body).age_group).toBeNull();
  });

  it('aborts pending submissions and prevents retries when revoked', async () => {
    localStorage.setItem(CITY_SHARING_KEY, 'true');
    let signal: AbortSignal;
    const fetcher = vi.fn((_url, options) => {
      signal = options.signal;
      return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('aborted'))));
    });
    vi.stubGlobal('fetch', fetcher);
    const request = logCityEvent('search', {});
    localStorage.setItem(CITY_SHARING_KEY, 'false'); revokeCityConsent();
    await request;
    expect(signal!.aborted).toBe(true); expect(fetcher).toHaveBeenCalledOnce();
  });
});
