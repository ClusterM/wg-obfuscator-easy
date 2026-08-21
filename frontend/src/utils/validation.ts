// Shared validation helpers used by client forms.

// Returns true if key is a valid WireGuard key (32 raw bytes in Base64).
export const isValidWireGuardKey = (key: string): boolean => {
  if (!key || typeof key !== 'string') return false;
  try {
    const raw = atob(key);
    if (raw.length !== 32) return false;
    return btoa(raw) === key;
  } catch {
    return false;
  }
};

// Strict IPv4 CIDR validation: the address must be the network address for the
// given prefix length (no host bits set), and /0 must be 0.0.0.0.
export const validateCidr = (cidr: string): boolean => {
  if (!cidr || typeof cidr !== 'string') return false;

  const trimmed = cidr.trim();
  if (!trimmed) return false;

  if (trimmed.indexOf('/') === -1 || trimmed.indexOf('/') !== trimmed.lastIndexOf('/')) {
    return false;
  }

  const [ip, mask] = trimmed.split('/');
  if (!ip || !mask) return false;

  const maskNum = parseInt(mask, 10);
  if (mask !== String(maskNum) || isNaN(maskNum) || maskNum < 0 || maskNum > 32) {
    return false;
  }

  const ipv4Regex = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
  const match = ip.match(ipv4Regex);
  if (!match) return false;

  for (let i = 1; i <= 4; i++) {
    const octet = parseInt(match[i], 10);
    if (isNaN(octet) || octet < 0 || octet > 255) {
      return false;
    }
  }

  if (maskNum === 0 && ip !== '0.0.0.0') {
    return false;
  }

  // Strict CIDR: host bits must be zero.
  const octets = ip.split('.').map((oct) => parseInt(oct, 10));
  for (let i = 0; i < 4; i++) {
    const bitsFromStart = i * 8;
    const bitsInOctet = Math.max(0, Math.min(8, maskNum - bitsFromStart));

    if (bitsInOctet === 0) {
      if (octets[i] !== 0) {
        return false;
      }
    } else if (bitsInOctet < 8) {
      const hostBits = 8 - bitsInOctet;
      const hostMask = (1 << hostBits) - 1;
      if ((octets[i] & hostMask) !== 0) {
        return false;
      }
    }
  }

  return true;
};
