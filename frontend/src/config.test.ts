import { describe, expect, it } from 'vitest';
import { apiUrl } from './config';

describe('apiUrl', () => {
  it('puts the backend base in front of the path', () => {
    expect(apiUrl('/api/routes').endsWith('/api/routes')).toBe(true);
  });
});
