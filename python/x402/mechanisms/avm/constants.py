"""AVM mechanism constants - network configs, ASA IDs, error codes."""

import os
from typing import TypedDict

# Scheme identifier
SCHEME_EXACT = "exact"

# Default token decimals for USDC on Algorand
DEFAULT_DECIMALS = 6

# Minimum transaction fee on Algorand (in microalgos)
MIN_TXN_FEE = 1000

# Maximum transactions in an atomic group
MAX_GROUP_SIZE = 16

# Maximum reasonable fee for fee payer transactions (16,000 microalgos)
# Equals MAX_GROUP_SIZE * MIN_TXN_FEE — the maximum pooled fee for a full group.
# Prevents fee extraction attacks on the facilitator's fee payer accounts.
MAX_REASONABLE_FEE = 16000

# Algorand address validation regex (58 character base32 with checksum)
AVM_ADDRESS_REGEX = r"^[A-Z2-7]{58}$"

# ============================================================================
# Algod API Endpoints
# ============================================================================

# Fallback Algod API endpoints (AlgoNode public endpoints)
FALLBACK_ALGOD_MAINNET = "https://mainnet-api.algonode.cloud"
FALLBACK_ALGOD_TESTNET = "https://testnet-api.algonode.cloud"

# Fallback Indexer API endpoints (AlgoNode public endpoints)
FALLBACK_INDEXER_MAINNET = "https://mainnet-idx.algonode.cloud"
FALLBACK_INDEXER_TESTNET = "https://testnet-idx.algonode.cloud"

# Algod URLs - check environment variables first, fall back to AlgoNode
# Set ALGOD_MAINNET_URL or ALGOD_TESTNET_URL to use custom endpoints
MAINNET_ALGOD_URL = os.environ.get("ALGOD_MAINNET_URL", FALLBACK_ALGOD_MAINNET)
TESTNET_ALGOD_URL = os.environ.get("ALGOD_TESTNET_URL", FALLBACK_ALGOD_TESTNET)

# Indexer URLs - check environment variables first, fall back to AlgoNode
# Set INDEXER_MAINNET_URL or INDEXER_TESTNET_URL to use custom endpoints
MAINNET_INDEXER_URL = os.environ.get("INDEXER_MAINNET_URL", FALLBACK_INDEXER_MAINNET)
TESTNET_INDEXER_URL = os.environ.get("INDEXER_TESTNET_URL", FALLBACK_INDEXER_TESTNET)

# USDC ASA IDs on Algorand
USDC_MAINNET_ASA_ID = 31566704
USDC_TESTNET_ASA_ID = 10458941

# Genesis hashes (base64 encoded)
MAINNET_GENESIS_HASH = "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="
TESTNET_GENESIS_HASH = "SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="

# CAIP-2 network identifiers for Algorand (V2)
ALGORAND_MAINNET_CAIP2 = f"algorand:{MAINNET_GENESIS_HASH}"
ALGORAND_TESTNET_CAIP2 = f"algorand:{TESTNET_GENESIS_HASH}"

# V1 to V2 network identifier mappings (for backwards compatibility)
V1_TO_V2_NETWORK_MAP: dict[str, str] = {
    "algorand-mainnet": ALGORAND_MAINNET_CAIP2,
    "algorand-testnet": ALGORAND_TESTNET_CAIP2,
    # Also support short names
    "algorand": ALGORAND_MAINNET_CAIP2,
}

# V2 to V1 network identifier mappings (for backwards compatibility)
V2_TO_V1_NETWORK_MAP: dict[str, str] = {
    ALGORAND_MAINNET_CAIP2: "algorand-mainnet",
    ALGORAND_TESTNET_CAIP2: "algorand-testnet",
}

# V1 supported networks (legacy name-based)
V1_NETWORKS = [
    "algorand-mainnet",
    "algorand-testnet",
]

# All supported CAIP-2 networks
SUPPORTED_NETWORKS = [
    ALGORAND_MAINNET_CAIP2,
    ALGORAND_TESTNET_CAIP2,
]

# Transaction type identifiers
TXN_TYPE_PAYMENT = "pay"
TXN_TYPE_ASSET_TRANSFER = "axfer"
TXN_TYPE_KEY_REGISTRATION = "keyreg"
TXN_TYPE_ASSET_CONFIG = "acfg"
TXN_TYPE_ASSET_FREEZE = "afrz"
TXN_TYPE_APPLICATION_CALL = "appl"

# Blocked transaction types for security
BLOCKED_TXN_TYPES = [
    TXN_TYPE_KEY_REGISTRATION,  # Prevents key registration attacks
]

# Error codes
ERR_UNSUPPORTED_SCHEME = "unsupported_scheme"
ERR_NETWORK_MISMATCH = "network_mismatch"
ERR_INVALID_PAYLOAD = "invalid_exact_avm_payload"
ERR_INVALID_PAYMENT_INDEX = "invalid_exact_avm_payload_payment_index"
ERR_GROUP_TOO_LARGE = "invalid_exact_avm_payload_group_too_large"
ERR_EMPTY_GROUP = "invalid_exact_avm_payload_empty_group"
ERR_GROUP_DECODE_FAILED = "invalid_exact_avm_payload_group_decode_failed"
ERR_TXN_DECODE_FAILED = "invalid_exact_avm_payload_transaction_decode_failed"
ERR_INVALID_TXN_TYPE = "invalid_exact_avm_payload_transaction_type"
ERR_BLOCKED_TXN_TYPE = "invalid_exact_avm_payload_blocked_transaction_type"
ERR_INVALID_ASSET_ID = "invalid_exact_avm_payload_asset_id_mismatch"
ERR_RECIPIENT_MISMATCH = "invalid_exact_avm_payload_recipient_mismatch"
ERR_AMOUNT_INSUFFICIENT = "invalid_exact_avm_payload_amount_insufficient"
ERR_INVALID_GROUP_ID = "invalid_exact_avm_payload_group_id_mismatch"
ERR_MISSING_GROUP_ID = "invalid_exact_avm_payload_missing_group_id"
ERR_MISSING_SIGNATURE = "invalid_exact_avm_payload_missing_signature"
ERR_INVALID_SIGNATURE = "invalid_exact_avm_payload_invalid_signature"
ERR_FEE_PAYER_MISSING = "invalid_exact_avm_payload_missing_fee_payer"
ERR_FEE_PAYER_NOT_MANAGED = "fee_payer_not_managed_by_facilitator"
ERR_FEE_PAYER_INVALID_TXN = "invalid_exact_avm_payload_fee_payer_transaction_invalid"
ERR_FEE_PAYER_TRANSFERRING = "invalid_exact_avm_payload_fee_payer_transferring_funds"
ERR_FEE_PAYER_HAS_AMOUNT = "invalid_exact_avm_payload_fee_payer_has_amount"
ERR_FEE_PAYER_HAS_CLOSE = "invalid_exact_avm_payload_fee_payer_has_close_to"
ERR_FEE_PAYER_HAS_REKEY = "invalid_exact_avm_payload_fee_payer_has_rekey_to"
ERR_SIMULATION_FAILED = "transaction_simulation_failed"
ERR_TRANSACTION_FAILED = "transaction_failed"
ERR_REKEY_DETECTED = "invalid_exact_avm_payload_rekey_detected"
ERR_CLOSE_TO_DETECTED = "invalid_exact_avm_payload_close_to_detected"
ERR_GENESIS_HASH_MISMATCH = "invalid_exact_avm_payload_genesis_hash_mismatch"


class AssetInfo(TypedDict):
    """Information about an Algorand Standard Asset (ASA)."""

    asa_id: int
    name: str
    decimals: int


class NetworkConfig(TypedDict):
    """Configuration for an Algorand network."""

    algod_url: str
    indexer_url: str
    genesis_hash: str
    genesis_id: str
    default_asset: AssetInfo


# Network configurations
NETWORK_CONFIGS: dict[str, NetworkConfig] = {
    # Algorand Mainnet
    ALGORAND_MAINNET_CAIP2: {
        "algod_url": MAINNET_ALGOD_URL,
        "indexer_url": MAINNET_INDEXER_URL,
        "genesis_hash": MAINNET_GENESIS_HASH,
        "genesis_id": "mainnet-v1.0",
        "default_asset": {
            "asa_id": USDC_MAINNET_ASA_ID,
            "name": "USDC",
            "decimals": 6,
        },
    },
    # Algorand Testnet
    ALGORAND_TESTNET_CAIP2: {
        "algod_url": TESTNET_ALGOD_URL,
        "indexer_url": TESTNET_INDEXER_URL,
        "genesis_hash": TESTNET_GENESIS_HASH,
        "genesis_id": "testnet-v1.0",
        "default_asset": {
            "asa_id": USDC_TESTNET_ASA_ID,
            "name": "USDC",
            "decimals": 6,
        },
    },
}

# Genesis hash to CAIP-2 mapping
GENESIS_HASH_TO_NETWORK: dict[str, str] = {
    MAINNET_GENESIS_HASH: ALGORAND_MAINNET_CAIP2,
    TESTNET_GENESIS_HASH: ALGORAND_TESTNET_CAIP2,
}
