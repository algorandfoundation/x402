"""BIP32-Ed25519 Hierarchical Deterministic Key Derivation.

Reference: BIP32-Ed25519 Hierarchical Deterministic Keys over a Non-linear Keyspace
https://acrobat.adobe.com/id/urn:aaid:sc:EU:04fe29b0-ea1a-478b-a886-9bb558a5242a

This implementation supports both:
- Standard BIP32-Ed25519 (Khovratovich) with 32 bits zeroed
- Peikert's amendment with 9 bits zeroed for more derivation levels
"""

from __future__ import annotations

import hashlib
import hmac
from enum import IntEnum
from typing import NamedTuple

from nacl.bindings import (
    crypto_core_ed25519_add,
    crypto_core_ed25519_scalar_add,
    crypto_core_ed25519_scalar_mul,
    crypto_core_ed25519_scalar_reduce,
    crypto_scalarmult_ed25519_base_noclamp,
)


class BIP32DerivationType(IntEnum):
    """BIP32 derivation type."""

    # Standard Ed25519 BIP32 derivations - zeroes 32 bits from each derived zL
    KHOVRATOVICH = 32
    # Peikert's amendment - zeroes only 9 bits from each derived zL
    PEIKERT = 9


# Hardening constant for BIP32 path indices
HARDENED_OFFSET = 0x80000000


def harden(num: int) -> int:
    """Create a hardened index for BIP32 derivation."""
    return HARDENED_OFFSET + num


class ExtendedKey(NamedTuple):
    """Extended key containing kL, kR, and chain code."""

    kL: bytes  # Left 32 bytes (scalar/private key)
    kR: bytes  # Right 32 bytes
    chain_code: bytes  # 32-byte chain code


def bytes_to_int_le(data: bytes) -> int:
    """Convert little-endian bytes to integer."""
    return int.from_bytes(data, byteorder="little")


def int_to_bytes_le(num: int, length: int) -> bytes:
    """Convert integer to little-endian bytes of specified length."""
    # Handle potential overflow by masking to the required bit width
    mask = (1 << (length * 8)) - 1
    num = num & mask
    return num.to_bytes(length, byteorder="little")


def trunc_256_minus_g_bits(data: bytes, g: int) -> bytes:
    """Truncate an array by zeroing the last g bits (little-endian).

    Args:
        data: 32-byte array
        g: Number of bits to zero from the end

    Returns:
        Array with the last g bits set to zero
    """
    if g < 0 or g > 256:
        raise ValueError("Number of bits to zero must be between 0 and 256.")

    result = bytearray(data)
    remaining_bits = g

    # Start from the last byte and move backward
    for i in range(len(result) - 1, -1, -1):
        if remaining_bits <= 0:
            break
        if remaining_bits >= 8:
            result[i] = 0
            remaining_bits -= 8
        else:
            # Zero out the most significant bits of this byte
            result[i] &= 0xFF >> remaining_bits
            break

    return bytes(result)


def from_seed(seed: bytes) -> ExtendedKey:
    """Derive root key from seed (BIP32-Ed25519 Section V.A).

    Args:
        seed: 32-byte seed from BIP39 mnemonic

    Returns:
        Extended root key (kL, kR, chain_code)
    """
    # k = H512(seed)
    k = hashlib.sha512(seed).digest()
    kL = bytearray(k[:32])
    kR = k[32:64]

    # While the third highest bit of the last byte of kL is not zero
    while (kL[31] & 0b00100000) != 0:
        k = hmac.new(bytes(kL), kR, hashlib.sha512).digest()
        kL = bytearray(k[:32])
        kR = k[32:64]

    # Clamp the key (set bits as per spec)
    # The lowest 3 bits of the first byte are cleared
    kL[0] &= 0b11111000
    # The highest bit of the last byte is cleared
    kL[31] &= 0b01111111
    # The second highest bit of the last byte is set
    kL[31] |= 0b01000000

    # Chain root code: SHA256(0x01 || seed)
    chain_code = hashlib.sha256(bytes([0x01]) + seed).digest()

    return ExtendedKey(kL=bytes(kL), kR=kR, chain_code=chain_code)


def _derive_non_hardened(
    kL: bytes, chain_code: bytes, index: int
) -> tuple[bytes, bytes]:
    """Derive non-hardened child key components.

    Args:
        kL: Left 32 bytes (scalar)
        chain_code: Chain code
        index: Non-hardened index (< 2^31)

    Returns:
        Tuple of (Z, child_chain_code)
    """
    # Compute public key from scalar
    pk = crypto_scalarmult_ed25519_base_noclamp(kL)

    # Build data: 0x02 || pk || index_le
    data = bytes([0x02]) + pk + index.to_bytes(4, byteorder="little")

    # Z = HMAC-SHA512(chain_code, data)
    z = hmac.new(chain_code, data, hashlib.sha512).digest()

    # Child chain code = right 32 bytes of HMAC-SHA512(chain_code, 0x03 || pk || index)
    data_cc = bytes([0x03]) + pk + index.to_bytes(4, byteorder="little")
    full_child_cc = hmac.new(chain_code, data_cc, hashlib.sha512).digest()
    child_chain_code = full_child_cc[32:64]

    return z, child_chain_code


def _derive_hardened(
    kL: bytes, kR: bytes, chain_code: bytes, index: int
) -> tuple[bytes, bytes]:
    """Derive hardened child key components.

    Args:
        kL: Left 32 bytes (scalar)
        kR: Right 32 bytes
        chain_code: Chain code
        index: Hardened index (>= 2^31)

    Returns:
        Tuple of (Z, child_chain_code)
    """
    # Build data: 0x00 || kL || kR || index_le
    data = bytes([0x00]) + kL + kR + index.to_bytes(4, byteorder="little")

    # Z = HMAC-SHA512(chain_code, data)
    z = hmac.new(chain_code, data, hashlib.sha512).digest()

    # Child chain code = right 32 bytes of HMAC-SHA512(chain_code, 0x01 || kL || kR || index)
    data_cc = bytes([0x01]) + kL + kR + index.to_bytes(4, byteorder="little")
    full_child_cc = hmac.new(chain_code, data_cc, hashlib.sha512).digest()
    child_chain_code = full_child_cc[32:64]

    return z, child_chain_code


def derive_child_node_private(
    extended_key: ExtendedKey,
    index: int,
    g: int = BIP32DerivationType.PEIKERT,
) -> ExtendedKey:
    """Derive child private key (BIP32-Ed25519 Section V.B & V.C).

    Args:
        extended_key: Extended key (kL, kR, chain_code)
        index: Child index (hardened if >= 2^31)
        g: Number of bits to zero (32 for Khovratovich, 9 for Peikert)

    Returns:
        Extended child key
    """
    kL = extended_key.kL
    kR = extended_key.kR
    cc = extended_key.chain_code

    # Step 1 & 3: Produce Z and child chain code based on hardening
    if index < HARDENED_OFFSET:
        z, child_chain_code = _derive_non_hardened(kL, cc, index)
    else:
        z, child_chain_code = _derive_hardened(kL, kR, cc, index)

    # Step 2: Compute child private key
    z_left = z[:32]
    z_right = z[32:64]

    # Truncate zL based on derivation type
    zL = trunc_256_minus_g_bits(z_left, g)

    # child_kL = kL + 8 * truncated(zLeft)
    kL_int = bytes_to_int_le(kL)
    zL_int = bytes_to_int_le(zL)

    child_kL_int = kL_int + (zL_int * 8)

    # Check if result is >= 2^255 (not safe)
    if child_kL_int >= (1 << 255):
        raise ValueError("zL * 8 is larger than 2^255, which is not safe")

    child_kL = int_to_bytes_le(child_kL_int, 32)

    # child_kR = kR + zRight (mod 2^256)
    kR_int = bytes_to_int_le(kR)
    zR_int = bytes_to_int_le(z_right)
    child_kR_int = (kR_int + zR_int) & ((1 << 256) - 1)
    child_kR = int_to_bytes_le(child_kR_int, 32)

    return ExtendedKey(kL=child_kL, kR=child_kR, chain_code=child_chain_code)


def derive_child_node_public(
    public_key: bytes,
    chain_code: bytes,
    index: int,
    g: int = BIP32DerivationType.PEIKERT,
) -> tuple[bytes, bytes]:
    """Derive child public key (BIP32-Ed25519 Section V.D).

    Args:
        public_key: 32-byte public key
        chain_code: 32-byte chain code
        index: Non-hardened index (< 2^31)
        g: Number of bits to zero (32 for Khovratovich, 9 for Peikert)

    Returns:
        Tuple of (child_public_key, child_chain_code)
    """
    if index >= HARDENED_OFFSET:
        raise ValueError("Cannot derive public key with hardened index")

    # Build data: 0x02 || pk || index_le
    data = bytes([0x02]) + public_key + index.to_bytes(4, byteorder="little")

    # Z = HMAC-SHA512(chain_code, data)
    z = hmac.new(chain_code, data, hashlib.sha512).digest()

    # Step 2: Compute child public key
    zL = trunc_256_minus_g_bits(z[:32], g)

    # childPk = pk + (8 * zL) * G
    zL_int = bytes_to_int_le(zL)
    scaled_zL = int_to_bytes_le(zL_int * 8, 32)
    p = crypto_scalarmult_ed25519_base_noclamp(scaled_zL)

    # Step 3: Compute child chain code
    data_cc = bytes([0x03]) + public_key + index.to_bytes(4, byteorder="little")
    full_child_cc = hmac.new(chain_code, data_cc, hashlib.sha512).digest()
    child_chain_code = full_child_cc[32:64]

    # Add points: childPk = p + pk
    child_pk = crypto_core_ed25519_add(p, public_key)

    return child_pk, child_chain_code


def derive_key(
    root_key: ExtendedKey,
    bip44_path: list[int],
    derivation_type: BIP32DerivationType = BIP32DerivationType.PEIKERT,
) -> ExtendedKey:
    """Derive a key from root key along a BIP44 path.

    Args:
        root_key: Root key from from_seed()
        bip44_path: List of indices (use harden() for hardened)
        derivation_type: Khovratovich (32) or Peikert (9)

    Returns:
        Extended private key
    """
    key = root_key
    g = int(derivation_type)

    for index in bip44_path:
        key = derive_child_node_private(key, index, g)

    return key


def get_public_key(extended_key: ExtendedKey) -> bytes:
    """Get public key from extended private key.

    Args:
        extended_key: Extended private key

    Returns:
        32-byte public key
    """
    return crypto_scalarmult_ed25519_base_noclamp(extended_key.kL)


def get_algorand_bip44_path(account: int = 0, key_index: int = 0) -> list[int]:
    """Get Algorand BIP44 path for the given account and key index.

    Standard Algorand path: m/44'/283'/account'/0/keyIndex

    Args:
        account: Account index (will be hardened)
        key_index: Key index (non-hardened)

    Returns:
        List of path indices
    """
    return [
        harden(44),  # Purpose
        harden(283),  # Algorand coin type
        harden(account),  # Account
        0,  # Change (external)
        key_index,  # Address index
    ]


def sign_with_extended_key(extended_key: ExtendedKey, message: bytes) -> bytes:
    """Sign a message with a BIP32-Ed25519 extended key.

    This implements EdDSA signing using the scalar (kL) and nonce key (kR)
    from the extended key, as per RFC 8032 but without re-hashing the key.

    Args:
        extended_key: Extended private key from derive_key()
        message: Message bytes to sign

    Returns:
        64-byte signature (R || S)
    """
    scalar = extended_key.kL  # 32 bytes - already clamped
    kR = extended_key.kR  # 32 bytes - used for deterministic nonce

    # Get public key from scalar
    public_key = crypto_scalarmult_ed25519_base_noclamp(scalar)

    # Step 1: r = H(kR || message) mod L
    # This is the deterministic nonce
    r_hash = hashlib.sha512(kR + message).digest()
    r = crypto_core_ed25519_scalar_reduce(r_hash)

    # Step 2: R = r * G
    R = crypto_scalarmult_ed25519_base_noclamp(r)

    # Step 3: h = H(R || A || message) mod L
    # This is the challenge
    h_hash = hashlib.sha512(R + public_key + message).digest()
    h = crypto_core_ed25519_scalar_reduce(h_hash)

    # Step 4: S = (r + h * scalar) mod L
    h_times_scalar = crypto_core_ed25519_scalar_mul(h, scalar)
    S = crypto_core_ed25519_scalar_add(r, h_times_scalar)

    # Signature is R || S
    return R + S
