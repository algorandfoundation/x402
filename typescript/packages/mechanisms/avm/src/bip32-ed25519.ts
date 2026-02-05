/**
 * BIP32-Ed25519 Hierarchical Deterministic Key Derivation
 *
 * Reference: BIP32-Ed25519 Hierarchical Deterministic Keys over a Non-linear Keyspace
 * https://acrobat.adobe.com/id/urn:aaid:sc:EU:04fe29b0-ea1a-478b-a886-9bb558a5242a
 *
 * This implementation supports both:
 * - Standard BIP32-Ed25519 (Khovratovich) with 32 bits zeroed
 * - Peikert's amendment with 9 bits zeroed for more derivation levels
 */

import { createHash, createHmac } from "crypto";
import { ed25519 } from "@noble/curves/ed25519";

// Ed25519 curve order (l)
const CURVE_ORDER =
  0x1000000000000000000000000000000014def9dea2f79cd65812631a5cf5d3edn;

/**
 * BIP32 derivation type
 */
export enum BIP32DerivationType {
  /** Standard Ed25519 BIP32 derivations - zeroes 32 bits from each derived zL */
  Khovratovich = 32,
  /** Peikert's amendment - zeroes only 9 bits from each derived zL */
  Peikert = 9,
}

/**
 * Hardening constant for BIP32 path indices
 */
export const HARDENED_OFFSET = 0x80000000;

/**
 * Create a hardened index for BIP32 derivation
 */
export function harden(num: number): number {
  return HARDENED_OFFSET + num;
}

/**
 * Convert a little-endian byte array to a BigInt
 */
function bytesToBigIntLE(bytes: Uint8Array): bigint {
  let result = 0n;
  for (let i = bytes.length - 1; i >= 0; i--) {
    result = (result << 8n) + BigInt(bytes[i]);
  }
  return result;
}

/**
 * Convert a BigInt to a little-endian byte array of specified length
 */
function bigIntToBytesLE(num: bigint, length: number): Uint8Array {
  const result = new Uint8Array(length);
  let remaining = num;
  for (let i = 0; i < length; i++) {
    result[i] = Number(remaining & 0xffn);
    remaining = remaining >> 8n;
  }
  return result;
}

/**
 * Ed25519 scalar multiplication with base point (no clamping)
 * This is equivalent to libsodium's crypto_scalarmult_ed25519_base_noclamp
 *
 * Unlike standard ed25519 operations, this doesn't clamp the scalar.
 * The scalar is reduced modulo the curve order if necessary.
 */
function scalarMultBase(scalar: Uint8Array): Uint8Array {
  // Convert little-endian scalar bytes to bigint
  let scalarBigInt = bytesToBigIntLE(scalar);

  // Reduce scalar modulo curve order if it's >= order
  // This matches libsodium's behavior
  if (scalarBigInt >= CURVE_ORDER) {
    scalarBigInt = scalarBigInt % CURVE_ORDER;
  }

  // Handle zero scalar case
  if (scalarBigInt === 0n) {
    // Return identity point (all zeros is not valid, but we handle edge case)
    return ed25519.ExtendedPoint.ZERO.toRawBytes();
  }

  // Multiply base point by scalar
  const point = ed25519.ExtendedPoint.BASE.multiply(scalarBigInt);

  // Convert to compressed point format (32 bytes)
  return point.toRawBytes();
}

/**
 * Ed25519 point addition
 * This is equivalent to libsodium's crypto_core_ed25519_add
 */
function pointAdd(p1: Uint8Array, p2: Uint8Array): Uint8Array {
  const point1 = ed25519.ExtendedPoint.fromHex(p1);
  const point2 = ed25519.ExtendedPoint.fromHex(p2);
  const result = point1.add(point2);
  return result.toRawBytes();
}

/**
 * Truncate an array by zeroing the last g bits (little-endian)
 *
 * @param array - An array of up to 256 bits
 * @param g - The number of bits to zero from the end
 * @returns The array with the last g bits set to zero
 */
function trunc256MinusGBits(array: Uint8Array, g: number): Uint8Array {
  if (g < 0 || g > 256) {
    throw new Error("Number of bits to zero must be between 0 and 256.");
  }

  const truncated = new Uint8Array(array);
  let remainingBits = g;

  // Start from the last byte and move backward
  for (let i = truncated.length - 1; i >= 0 && remainingBits > 0; i--) {
    if (remainingBits >= 8) {
      truncated[i] = 0;
      remainingBits -= 8;
    } else {
      // Zero out the most significant bits of this byte
      truncated[i] &= 0xff >> remainingBits;
      break;
    }
  }

  return truncated;
}

/**
 * Derive root key from seed (BIP32-Ed25519 Section V.A)
 *
 * @param seed - Seed bytes (typically 32 or 64 bytes from BIP39)
 * @returns Extended root key (kL, kR, c) - 96 bytes total
 */
export function fromSeed(seed: Uint8Array): Uint8Array {
  // k = H512(seed)
  let k = createHash("sha512").update(seed).digest();
  let kL = k.subarray(0, 32);
  let kR = k.subarray(32, 64);

  // While the third highest bit of the last byte of kL is not zero
  while ((kL[31] & 0b00100000) !== 0) {
    k = createHmac("sha512", kL).update(kR).digest();
    kL = k.subarray(0, 32);
    kR = k.subarray(32, 64);
  }

  // Clone kL since we're modifying it
  const kLClamped = Buffer.from(kL);

  // Clamp the key (set bits as per spec)
  // The lowest 3 bits of the first byte are cleared
  kLClamped[0] &= 0b11111000;
  // The highest bit of the last byte is cleared
  kLClamped[31] &= 0b01111111;
  // The second highest bit of the last byte is set
  kLClamped[31] |= 0b01000000;

  // Chain root code: SHA256(0x01 || seed)
  const c = createHash("sha256")
    .update(Buffer.concat([new Uint8Array([0x01]), seed]))
    .digest();

  return new Uint8Array(Buffer.concat([kLClamped, kR, c]));
}

/**
 * Derive non-hardened child key components
 *
 * @param kL - Left 32 bytes (scalar)
 * @param cc - Chain code
 * @param index - Non-hardened index (< 2^31)
 * @returns Z and child chain code
 */
function deriveNonHardened(
  kL: Uint8Array,
  cc: Uint8Array,
  index: number,
): { z: Uint8Array; childChainCode: Uint8Array } {
  const data = Buffer.alloc(1 + 32 + 4);
  data.writeUInt32LE(index, 1 + 32);

  // Compute public key from scalar
  const pk = scalarMultBase(kL);
  pk.forEach((byte, i) => {
    data[1 + i] = byte;
  });

  // Z = HMAC-SHA512(cc, 0x02 || pk || index)
  data[0] = 0x02;
  const z = createHmac("sha512", cc).update(data).digest();

  // Child chain code = right 32 bytes of HMAC-SHA512(cc, 0x03 || pk || index)
  data[0] = 0x03;
  const fullChildChainCode = createHmac("sha512", cc).update(data).digest();
  const childChainCode = fullChildChainCode.subarray(32, 64);

  return { z, childChainCode };
}

/**
 * Derive hardened child key components
 *
 * @param kL - Left 32 bytes (scalar)
 * @param kR - Right 32 bytes
 * @param cc - Chain code
 * @param index - Hardened index (>= 2^31)
 * @returns Z and child chain code
 */
function deriveHardened(
  kL: Uint8Array,
  kR: Uint8Array,
  cc: Uint8Array,
  index: number,
): { z: Uint8Array; childChainCode: Uint8Array } {
  const data = Buffer.alloc(1 + 64 + 4);
  data.writeUInt32LE(index, 1 + 64);

  Buffer.from(kL).copy(data, 1);
  Buffer.from(kR).copy(data, 1 + 32);

  // Z = HMAC-SHA512(cc, 0x00 || kL || kR || index)
  data[0] = 0x00;
  const z = createHmac("sha512", cc).update(data).digest();

  // Child chain code = right 32 bytes of HMAC-SHA512(cc, 0x01 || kL || kR || index)
  data[0] = 0x01;
  const fullChildChainCode = createHmac("sha512", cc).update(data).digest();
  const childChainCode = fullChildChainCode.subarray(32, 64);

  return { z, childChainCode };
}

/**
 * Derive child private key (BIP32-Ed25519 Section V.B & V.C)
 *
 * @param extendedKey - Extended key (kL, kR, c) - 96 bytes
 * @param index - Child index (hardened if >= 2^31)
 * @param g - Number of bits to zero (32 for Khovratovich, 9 for Peikert)
 * @returns Extended child key (kL, kR, c) - 96 bytes
 */
export function deriveChildNodePrivate(
  extendedKey: Uint8Array,
  index: number,
  g: number = BIP32DerivationType.Peikert,
): Uint8Array {
  const kL = extendedKey.subarray(0, 32);
  const kR = extendedKey.subarray(32, 64);
  const cc = extendedKey.subarray(64, 96);

  // Step 1 & 3: Produce Z and child chain code based on hardening
  const { z, childChainCode } =
    index < HARDENED_OFFSET
      ? deriveNonHardened(kL, cc, index)
      : deriveHardened(kL, kR, cc, index);

  // Step 2: Compute child private key
  const zLeft = z.subarray(0, 32);
  const zRight = z.subarray(32, 64);

  // Truncate zL based on derivation type
  const zL = trunc256MinusGBits(zLeft, g);

  // zL = kL + 8 * truncated(zLeft)
  const klBigNum = bytesToBigIntLE(kL);
  const zlBigNum = bytesToBigIntLE(zL);
  const big8 = 8n;

  const zlMul8 = klBigNum + zlBigNum * big8;

  // Check if zlMul8 is >= 2^255 (not safe)
  if (zlMul8 >= 1n << 255n) {
    throw new Error("zL * 8 is larger than 2^255, which is not safe");
  }

  const left = bigIntToBytesLE(zlMul8, 32);

  // zR = kR + zRight (mod 2^256)
  const krBigNum = bytesToBigIntLE(kR);
  const zrBigNum = bytesToBigIntLE(zRight);
  const rightBigNum = (krBigNum + zrBigNum) & ((1n << 256n) - 1n);
  const right = bigIntToBytesLE(rightBigNum, 32);

  return new Uint8Array(Buffer.concat([left, right, childChainCode]));
}

/**
 * Derive child public key (BIP32-Ed25519 Section V.D)
 *
 * @param extendedPublicKey - Extended public key (pk, c) - 64 bytes
 * @param index - Non-hardened index (< 2^31)
 * @param g - Number of bits to zero (32 for Khovratovich, 9 for Peikert)
 * @returns Extended child public key (pk, c) - 64 bytes
 */
export function deriveChildNodePublic(
  extendedPublicKey: Uint8Array,
  index: number,
  g: number = BIP32DerivationType.Peikert,
): Uint8Array {
  if (index >= HARDENED_OFFSET) {
    throw new Error("Cannot derive public key with hardened index");
  }

  const pk = extendedPublicKey.subarray(0, 32);
  const cc = extendedPublicKey.subarray(32, 64);

  const data = Buffer.alloc(1 + 32 + 4);
  data.writeUInt32LE(index, 1 + 32);
  Buffer.from(pk).copy(data, 1);

  // Step 1: Compute Z
  data[0] = 0x02;
  const z = createHmac("sha512", cc).update(data).digest();

  // Step 2: Compute child public key
  const zL = trunc256MinusGBits(z.subarray(0, 32), g);

  // childPk = pk + (8 * zL) * G
  const zlBigNum = bytesToBigIntLE(zL);
  const scaledZL = bigIntToBytesLE(zlBigNum * 8n, 32);
  const p = scalarMultBase(scaledZL);

  // Step 3: Compute child chain code
  data[0] = 0x03;
  const fullChildChainCode = createHmac("sha512", cc).update(data).digest();
  const childChainCode = fullChildChainCode.subarray(32, 64);

  // Add points: childPk = p + pk
  const childPk = pointAdd(p, pk);

  return new Uint8Array(Buffer.concat([childPk, childChainCode]));
}

/**
 * Derive a key from root key along a BIP44 path
 *
 * @param rootKey - Root key from fromSeed() - 96 bytes
 * @param bip44Path - Array of indices (use harden() for hardened)
 * @param derivationType - Khovratovich (32) or Peikert (9)
 * @returns Extended private key (kL, kR, c) - 96 bytes
 */
export function deriveKey(
  rootKey: Uint8Array,
  bip44Path: number[],
  derivationType: BIP32DerivationType = BIP32DerivationType.Peikert,
): Uint8Array {
  let key = rootKey;
  const g = derivationType;

  for (const index of bip44Path) {
    key = deriveChildNodePrivate(key, index, g);
  }

  return key;
}

/**
 * Get public key from extended private key
 *
 * @param extendedPrivateKey - Extended private key (kL, kR, c) - 96 bytes
 * @returns 32-byte public key
 */
export function getPublicKey(extendedPrivateKey: Uint8Array): Uint8Array {
  const scalar = extendedPrivateKey.subarray(0, 32);
  return scalarMultBase(scalar);
}

/**
 * Get Algorand BIP44 path for the given account and key index
 *
 * Standard Algorand path: m/44'/283'/account'/0/keyIndex
 *
 * @param account - Account index (will be hardened)
 * @param keyIndex - Key index (non-hardened)
 * @returns Array of path indices
 */
export function getAlgorandBIP44Path(
  account: number = 0,
  keyIndex: number = 0,
): number[] {
  return [
    harden(44), // Purpose
    harden(283), // Algorand coin type
    harden(account), // Account
    0, // Change (external)
    keyIndex, // Address index
  ];
}

/**
 * Reduce a 64-byte hash to a scalar modulo the curve order
 * This is equivalent to libsodium's crypto_core_ed25519_scalar_reduce
 */
function scalarReduce(hash: Uint8Array): Uint8Array {
  const hashBigInt = bytesToBigIntLE(hash);
  const reduced = hashBigInt % CURVE_ORDER;
  return bigIntToBytesLE(reduced, 32);
}

/**
 * Add two scalars modulo the curve order
 * This is equivalent to libsodium's crypto_core_ed25519_scalar_add
 */
function scalarAdd(a: Uint8Array, b: Uint8Array): Uint8Array {
  const aBigInt = bytesToBigIntLE(a);
  const bBigInt = bytesToBigIntLE(b);
  const sum = (aBigInt + bBigInt) % CURVE_ORDER;
  return bigIntToBytesLE(sum, 32);
}

/**
 * Multiply two scalars modulo the curve order
 * This is equivalent to libsodium's crypto_core_ed25519_scalar_mul
 */
function scalarMul(a: Uint8Array, b: Uint8Array): Uint8Array {
  const aBigInt = bytesToBigIntLE(a);
  const bBigInt = bytesToBigIntLE(b);
  const product = (aBigInt * bBigInt) % CURVE_ORDER;
  return bigIntToBytesLE(product, 32);
}

/**
 * Sign a message with a BIP32-Ed25519 extended key
 *
 * This implements EdDSA signing using the scalar (kL) and nonce key (kR)
 * from the extended key, as per RFC 8032 but without re-hashing the key.
 *
 * IMPORTANT: This function must be used for signing with BIP32-Ed25519 derived keys
 * because algosdk's standard signing re-hashes the key, which produces incorrect
 * signatures for pre-derived scalars.
 *
 * @param extendedKey - Extended private key from deriveKey() - 96 bytes (kL, kR, chainCode)
 * @param message - Message bytes to sign
 * @returns 64-byte signature (R || S)
 */
export function signWithExtendedKey(
  extendedKey: Uint8Array,
  message: Uint8Array,
): Uint8Array {
  const scalar = extendedKey.subarray(0, 32); // kL - already clamped
  const kR = extendedKey.subarray(32, 64); // Used for deterministic nonce

  // Get public key from scalar
  const publicKey = scalarMultBase(scalar);

  // Step 1: r = H(kR || message) mod L
  // This is the deterministic nonce
  const rHash = createHash("sha512")
    .update(Buffer.concat([kR, message]))
    .digest();
  const r = scalarReduce(rHash);

  // Step 2: R = r * G
  const R = scalarMultBase(r);

  // Step 3: h = H(R || A || message) mod L
  // This is the challenge
  const hHash = createHash("sha512")
    .update(Buffer.concat([R, publicKey, message]))
    .digest();
  const h = scalarReduce(hHash);

  // Step 4: S = (r + h * scalar) mod L
  const hTimesScalar = scalarMul(h, scalar);
  const S = scalarAdd(r, hTimesScalar);

  // Signature is R || S (64 bytes)
  return new Uint8Array(Buffer.concat([R, S]));
}
