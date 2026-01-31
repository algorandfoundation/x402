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

Usage:
    ```python
    from x402.mechanisms.avm import (
        ALGORAND_MAINNET_CAIP2,
        AlgorandSigner,
    )
    from x402.mechanisms.avm.exact import ExactAvmScheme

    # Client-side
    signer = AlgorandSigner.from_mnemonic("word1 word2 ... word25")
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
    # Submodules
    "exact",
]
