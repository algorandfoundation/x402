"""AVM (Algorand) Mnemonic Utilities for x402 Payment Protocol.

Supports both Algorand native 25-word mnemonics and BIP-39 24-word mnemonics.
BIP-39 mnemonics use BIP32-Ed25519 derivation with the Algorand derivation path.

See:
    - https://acrobat.adobe.com/id/urn:aaid:sc:EU:04fe29b0-ea1a-478b-a886-9bb558a5242a - BIP32-Ed25519 spec
    - https://github.com/satoshilabs/slips/blob/master/slip-0044.md - Coin type 283 = Algorand
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple

if TYPE_CHECKING:
    pass

# Check for optional dependencies
try:
    from bip_utils import (
        Bip39MnemonicValidator,
        Bip39SeedGenerator,
    )

    BIP_UTILS_AVAILABLE = True
except ImportError:
    BIP_UTILS_AVAILABLE = False

try:
    from algosdk import mnemonic as algo_mnemonic

    ALGOSDK_AVAILABLE = True
except ImportError:
    ALGOSDK_AVAILABLE = False


# Algorand BIP-44 derivation path
# m/44'/283'/0'/0/0
# - 44' = BIP-44 purpose
# - 283' = Algorand coin type (registered in SLIP-44)
# - 0' = account index
# - 0 = change (external chain, non-hardened)
# - 0 = address index (non-hardened)
#
# Note: Uses BIP32-Ed25519 derivation (Khovratovich/Peikert specification).
# This provides proper ed25519 HD key derivation with both hardened and non-hardened support.
ALGORAND_DERIVATION_PATH = "m/44'/283'/0'/0/0"


# Mnemonic type detection result
MnemonicType = Literal["algorand-25", "bip39-24", "invalid"]


class AlgorandAccount(NamedTuple):
    """Algorand account with address and secret key."""

    address: str
    private_key: str  # Base64-encoded private key (algosdk format)
    # Extended key for BIP32-Ed25519 derived accounts (needed for proper signing)
    # Format: base64(kL || kR) - 64 bytes total
    extended_key: str | None = None


def _check_algosdk() -> None:
    """Check that algosdk is available."""
    if not ALGOSDK_AVAILABLE:
        raise ImportError(
            "AVM mechanism requires py-algorand-sdk. Install with: pip install x402[avm]"
        )


def _check_bip_utils() -> None:
    """Check that bip_utils is available."""
    if not BIP_UTILS_AVAILABLE:
        raise ImportError(
            "BIP-39 mnemonic support requires bip_utils. "
            "Install with: pip install bip_utils"
        )


def detect_mnemonic_type(mnemonic: str) -> MnemonicType:
    """Detect the type of mnemonic based on word count and validity.

    Args:
        mnemonic: The mnemonic phrase to check.

    Returns:
        The detected mnemonic type:
        - "algorand-25" for valid Algorand 25-word mnemonics
        - "bip39-24" for valid BIP-39 24-word mnemonics
        - "invalid" for invalid or unsupported mnemonics

    Example:
        >>> detect_mnemonic_type("abandon abandon ... about")  # 24 words
        'bip39-24'
        >>> detect_mnemonic_type("abandon abandon ... abandon about")  # 25 words
        'algorand-25'
        >>> detect_mnemonic_type("invalid mnemonic")
        'invalid'
    """
    words = mnemonic.strip().split()

    if len(words) == 25:
        # Algorand native 25-word mnemonic
        _check_algosdk()
        try:
            algo_mnemonic.to_private_key(mnemonic)
            return "algorand-25"
        except Exception:
            return "invalid"

    if len(words) == 24:
        # BIP-39 24-word mnemonic
        if BIP_UTILS_AVAILABLE:
            if Bip39MnemonicValidator().IsValid(mnemonic):
                return "bip39-24"
        return "invalid"

    return "invalid"


def derive_algorand_from_bip39(
    mnemonic: str,
    account_index: int = 0,
) -> AlgorandAccount:
    """Derive an Algorand account from a BIP-39 24-word mnemonic.

    Uses BIP32-Ed25519 derivation with the standard Algorand derivation path.
    This is compatible with wallets like Lute, Pera, Defly, and other BIP-39
    compatible Algorand wallets.

    Args:
        mnemonic: BIP-39 24-word mnemonic phrase.
        account_index: Optional account index (default: 0).

    Returns:
        AlgorandAccount with address and private_key.

    Raises:
        ImportError: If bip_utils is not installed.
        ValueError: If the mnemonic is invalid.

    Example:
        >>> account = derive_algorand_from_bip39("abandon abandon ... about")
        >>> print(account.address)  # Algorand address
    """
    _check_bip_utils()
    _check_algosdk()

    import base64

    from algosdk import encoding

    from .bip32_ed25519 import (
        BIP32DerivationType,
        derive_key,
        from_seed,
        get_algorand_bip44_path,
        get_public_key,
    )

    # Validate the mnemonic
    if not Bip39MnemonicValidator().IsValid(mnemonic):
        raise ValueError("Invalid BIP-39 mnemonic phrase")

    # Convert mnemonic to seed (BIP-39) - this produces 64 bytes
    # BIP32-Ed25519 can work with any size seed (it hashes with SHA-512)
    seed = bytes(Bip39SeedGenerator(mnemonic).Generate())

    # Derive the root key using BIP32-Ed25519
    root_key = from_seed(seed)

    # Get the BIP44 path for Algorand
    bip44_path = get_algorand_bip44_path(0, account_index)

    # Derive the key at the specified path using Peikert derivation (9 bits)
    # This allows for more derivation levels while maintaining security
    derived_key = derive_key(root_key, bip44_path, BIP32DerivationType.PEIKERT)

    # Get the public key from the derived extended key
    public_key = get_public_key(derived_key)

    # The derived scalar (kL) is the private key
    private_key_seed = derived_key.kL

    # Algorand's secret key format is 64 bytes: [32-byte seed | 32-byte public key]
    # This matches the NaCl sign.keyPair.fromSeed format used internally by algosdk
    secret_key = private_key_seed + public_key

    # Encode as base64 for algosdk compatibility
    private_key_b64 = base64.b64encode(secret_key).decode("utf-8")

    # Store the extended key (kL || kR) for proper BIP32-Ed25519 signing
    # Standard algosdk signing won't work correctly with BIP32-Ed25519 keys
    extended_key_bytes = derived_key.kL + derived_key.kR
    extended_key_b64 = base64.b64encode(extended_key_bytes).decode("utf-8")

    # Get the address from the public key
    address = encoding.encode_address(public_key)

    return AlgorandAccount(
        address=address,
        private_key=private_key_b64,
        extended_key=extended_key_b64,
    )


def mnemonic_to_algorand_account(
    mnemonic: str,
    account_index: int = 0,
) -> AlgorandAccount:
    """Convert any supported mnemonic format to an Algorand account.

    Automatically detects whether the input is a 25-word Algorand native mnemonic
    or a 24-word BIP-39 mnemonic and derives the account accordingly.

    Args:
        mnemonic: Mnemonic phrase (24 or 25 words).
        account_index: Account index for BIP-39 derivation (ignored for 25-word mnemonics).

    Returns:
        AlgorandAccount with address and private_key (base64-encoded).

    Raises:
        ValueError: If the mnemonic is invalid or unsupported.
        ImportError: If required dependencies are not installed.

    Example:
        >>> # Works with Algorand native 25-word mnemonic
        >>> account1 = mnemonic_to_algorand_account("abandon abandon ... abandon about")
        >>>
        >>> # Also works with BIP-39 24-word mnemonic
        >>> account2 = mnemonic_to_algorand_account("abandon abandon ... about")
        >>>
        >>> # Derive additional accounts from BIP-39 mnemonic
        >>> account3 = mnemonic_to_algorand_account("abandon abandon ... about", 1)
    """
    _check_algosdk()

    words = mnemonic.strip().split()
    word_count = len(words)

    # Check for 24-word mnemonic without bip_utils installed
    if word_count == 24 and not BIP_UTILS_AVAILABLE:
        raise ImportError(
            "24-word BIP-39 mnemonic detected but bip_utils is not installed. "
            "Install with: pip install bip_utils"
        )

    mnemonic_type = detect_mnemonic_type(mnemonic)

    if mnemonic_type == "algorand-25":
        # Algorand native mnemonic - use algosdk directly
        # Note: account_index is ignored for 25-word mnemonics as they encode a single key
        from algosdk import account
        private_key = algo_mnemonic.to_private_key(mnemonic)
        address = account.address_from_private_key(private_key)
        return AlgorandAccount(address=address, private_key=private_key)

    if mnemonic_type == "bip39-24":
        # BIP-39 mnemonic - use BIP32-Ed25519 derivation
        return derive_algorand_from_bip39(mnemonic, account_index)

    raise ValueError(
        f"Invalid mnemonic ({word_count} words): must be a valid 24-word BIP-39 mnemonic or "
        "25-word Algorand mnemonic"
    )


def is_valid_mnemonic(mnemonic: str) -> bool:
    """Validate a mnemonic phrase.

    Args:
        mnemonic: The mnemonic phrase to validate.

    Returns:
        True if the mnemonic is valid (either 24-word BIP-39 or 25-word Algorand).

    Example:
        >>> is_valid_mnemonic("abandon abandon ... about")  # BIP-39
        True
        >>> is_valid_mnemonic("abandon abandon ... abandon about")  # Algorand
        True
        >>> is_valid_mnemonic("invalid words")
        False
    """
    return detect_mnemonic_type(mnemonic) != "invalid"


def get_mnemonic_word_count(mnemonic: str) -> int:
    """Get the word count from a mnemonic phrase.

    Args:
        mnemonic: The mnemonic phrase.

    Returns:
        Number of words in the mnemonic.
    """
    return len(mnemonic.strip().split())
