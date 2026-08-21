import { describe, it, expect } from 'vitest';
import { isValidWireGuardKey, validateCidr } from './validation';

describe('isValidWireGuardKey', () => {
  it('accepts a valid 32-byte Base64 key', () => {
    expect(isValidWireGuardKey('cOTGfq3o2upkUVFsyGAx/WoFlcpSlNQnUYyww9HF+Vs=')).toBe(true);
  });

  it('rejects too-short input', () => {
    expect(isValidWireGuardKey('short')).toBe(false);
  });

  it('rejects empty input', () => {
    expect(isValidWireGuardKey('')).toBe(false);
  });
});

describe('validateCidr', () => {
  it('accepts a default route', () => {
    expect(validateCidr('0.0.0.0/0')).toBe(true);
  });

  it('accepts a proper network address', () => {
    expect(validateCidr('192.168.1.0/24')).toBe(true);
  });

  it('rejects host bits set', () => {
    expect(validateCidr('192.168.1.5/24')).toBe(false);
  });

  it('rejects /0 that is not 0.0.0.0', () => {
    expect(validateCidr('1.2.3.4/0')).toBe(false);
  });

  it('rejects out-of-range octets', () => {
    expect(validateCidr('999.1.1.0/24')).toBe(false);
  });

  it('rejects missing mask', () => {
    expect(validateCidr('10.0.0.0')).toBe(false);
  });

  it('rejects IPv6 (current limitation)', () => {
    expect(validateCidr('::/0')).toBe(false);
  });

  it('rejects empty input', () => {
    expect(validateCidr('')).toBe(false);
  });
});
