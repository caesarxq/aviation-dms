import { describe, expect, it, beforeEach } from 'vitest';
import { clearIdentity, getIdentity, setIdentity } from './identity';

beforeEach(() => localStorage.clear());

describe('frontend identity profile', () => {
  it('defaults to the seeded system administrator profile', () => {
    expect(getIdentity()).toEqual({ role: 'system_admin', actor: 'admin' });
  });

  it('persists an explicitly selected profile', () => {
    setIdentity({ role: 'head_quality', actor: 'u-quality' });
    expect(getIdentity()).toEqual({ role: 'head_quality', actor: 'u-quality' });
  });

  it('clears the selected profile back to the safe development default', () => {
    setIdentity({ role: 'head_quality', actor: 'u-quality' });
    clearIdentity();
    expect(getIdentity()).toEqual({ role: 'system_admin', actor: 'admin' });
  });
});
