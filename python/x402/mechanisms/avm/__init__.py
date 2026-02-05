"""AVM (Algorand Virtual Machine) mechanism for x402 Python SDK.

This module provides Algorand blockchain integration for the x402 payment protocol.
It supports both V2 (CAIP-2 network identifiers) and V1 (legacy network names)
through backward compatibility wrappers.

Features:
- Atomic transaction groups (up to 16 transactions)
- ASA (Algorand Standard Assets) transfers
- Optional fee abstraction (gasless transactions)
- Instant finality (no consensus forks)
- Ed25519 signature verification
- BIP-39 24-word mnemonic support (Pera, Defly compatible)
- Algorand native 25-word mnemonic support
- Configurable Algod/Indexer URLs via environment variables

Environment Variables:
    ALGOD_MAINNET_URL: Custom Algod URL for mainnet (default: AlgoNode)
    ALGOD_TESTNET_URL: Custom Algod URL for testnet (default: AlgoNode)
    INDEXER_MAINNET_URL: Custom Indexer URL for mainnet (default: AlgoNode)
    INDEXER_TESTNET_URL: Custom Indexer URL for testnet (default: AlgoNode)

Usage:
    ```python
    from x402.mechanisms.avm import (
        ALGORAND_MAINNET_CAIP2,
        AlgorandSigner,
    )
    from x402.mechanisms.avm.exact import ExactAvmScheme

    # Client-side with 25-word Algorand mnemonic
    signer = AlgorandSigner.from_mnemonic("word1 word2 ... word25")

    # Or with 24-word BIP-39 mnemonic (Pera, Defly compatible)
    signer = AlgorandSigner.from_mnemonic("word1 word2 ... word24")

    client = x402Client()
    client.register("algorand:*", ExactAvmScheme(signer))
    ```
"""

# Constants
from .constants import (
    ALGORAND_MAINNET_CAIP2,
    ALGORAND_TESTNET_CAIP2,
    DEFAULT_DECIMALS,
    MAX_GROUP_SIZE,
    MIN_TXN_FEE,
    NETWORK_CONFIGS,
    SCHEME_EXACT,
    SUPPORTED_NETWORKS,
    USDC_MAINNET_ASA_ID,
    USDC_TESTNET_ASA_ID,
    V1_NETWORKS,
    V1_TO_V2_NETWORK_MAP,
)

# Types
from .types import (
    DecodedTransactionInfo,
    ExactAvmPayload,
    ExactAvmPayloadV1,
    ExactAvmPayloadV2,
    TransactionGroupInfo,
)

# Signer protocols
from .signer import (
    ClientAvmSigner,
    FacilitatorAvmSigner,
)

# Signer implementations
from .signers import (
    AlgorandSigner,
    FacilitatorAlgorandSigner,
)

# Utilities
from .utils import (
    decode_base64_transaction,
    decode_payment_group,
    decode_transaction_bytes,
    encode_transaction_group,
    from_atomic_amount,
    get_genesis_hash,
    get_network_config,
    get_usdc_asa_id,
    is_valid_address,
    is_valid_network,
    network_from_genesis_hash,
    normalize_network,
    parse_money_to_decimal,
    to_atomic_amount,
    validate_fee_payer_transaction,
    validate_no_security_risks,
)

# Mnemonic utilities
from .mnemonic import (
    ALGORAND_DERIVATION_PATH,
    AlgorandAccount,
    derive_algorand_from_bip39,
    detect_mnemonic_type,
    get_mnemonic_word_count,
    is_valid_mnemonic,
    mnemonic_to_algorand_account,
)

# BIP32-Ed25519 HD key derivation
from .bip32_ed25519 import (
    BIP32DerivationType,
    ExtendedKey,
    HARDENED_OFFSET,
    derive_child_node_private,
    derive_child_node_public,
    derive_key,
    from_seed,
    get_algorand_bip44_path,
    get_public_key,
    harden,
    sign_with_extended_key,
)

# Submodule exports
from . import exact

__all__ = [
    # Constants
    "ALGORAND_MAINNET_CAIP2",
    "ALGORAND_TESTNET_CAIP2",
    "DEFAULT_DECIMALS",
    "MAX_GROUP_SIZE",
    "MIN_TXN_FEE",
    "NETWORK_CONFIGS",
    "SCHEME_EXACT",
    "SUPPORTED_NETWORKS",
    "USDC_MAINNET_ASA_ID",
    "USDC_TESTNET_ASA_ID",
    "V1_NETWORKS",
    "V1_TO_V2_NETWORK_MAP",
    # Types
    "DecodedTransactionInfo",
    "ExactAvmPayload",
    "ExactAvmPayloadV1",
    "ExactAvmPayloadV2",
    "TransactionGroupInfo",
    # Signer protocols
    "ClientAvmSigner",
    "FacilitatorAvmSigner",
    # Signer implementations
    "AlgorandSigner",
    "FacilitatorAlgorandSigner",
    # Utilities
    "decode_base64_transaction",
    "decode_payment_group",
    "decode_transaction_bytes",
    "encode_transaction_group",
    "from_atomic_amount",
    "get_genesis_hash",
    "get_network_config",
    "get_usdc_asa_id",
    "is_valid_address",
    "is_valid_network",
    "network_from_genesis_hash",
    "normalize_network",
    "parse_money_to_decimal",
    "to_atomic_amount",
    "validate_fee_payer_transaction",
    "validate_no_security_risks",
    # Mnemonic utilities
    "ALGORAND_DERIVATION_PATH",
    "AlgorandAccount",
    "derive_algorand_from_bip39",
    "detect_mnemonic_type",
    "get_mnemonic_word_count",
    "is_valid_mnemonic",
    "mnemonic_to_algorand_account",
    # BIP32-Ed25519 HD key derivation
    "BIP32DerivationType",
    "ExtendedKey",
    "HARDENED_OFFSET",
    "derive_child_node_private",
    "derive_child_node_public",
    "derive_key",
    "from_seed",
    "get_algorand_bip44_path",
    "get_public_key",
    "harden",
    "sign_with_extended_key",
    # Submodules
    "exact",
]
