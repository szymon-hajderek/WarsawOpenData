import { afterEach, describe, expect, it, vi } from 'vitest';
import { logJourney, type JourneySubmission } from './journeys';

const body: JourneySubmission = {
  token: 'eeb72c86-c566-4c0c-85b6-bc1ab20c13a7',
  from: { id: 'ztm:700901', position: [52.2, 21], isCurrentLocation: false },
  to: { id: 'vet:203610', position: [52.3, 21.1], isCurrentLocation: false },
};

afterEach(() => { vi.unstubAllGlobals(); });

describe('statistics submission', () => {
  it('retries a lost response with exactly the same body and token', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error('lost response')).mockResolvedValueOnce({ ok: true });
    vi.stubGlobal('fetch', fetch);
    expect(await logJourney(body, new AbortController().signal)).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
  });

  it('does not retry after consent is revoked', async () => {
    const controller = new AbortController();
    const fetch = vi.fn().mockImplementation(async () => { controller.abort(); throw new Error('offline'); });
    vi.stubGlobal('fetch', fetch);
    expect(await logJourney(body, controller.signal)).toBe(false);
    expect(fetch).toHaveBeenCalledOnce();
  });
});
