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
- Configurable Algod/Indexer URLs via environment variables

Environment Variables:
    ALGOD_MAINNET_URL: Custom Algod URL for mainnet (default: AlgoNode)
    ALGOD_TESTNET_URL: Custom Algod URL for testnet (default: AlgoNode)
    INDEXER_MAINNET_URL: Custom Indexer URL for mainnet (default: AlgoNode)
    INDEXER_TESTNET_URL: Custom Indexer URL for testnet (default: AlgoNode)

Usage:
    ```python
    import base64
    import algosdk
    from x402.mechanisms.avm import (
        ALGORAND_MAINNET_CAIP2,
        ClientAvmSigner,
    )
    from x402.mechanisms.avm.exact import ExactAvmScheme

    # Implement ClientAvmSigner with algosdk
    class MyAlgorandSigner:
        def __init__(self, private_key_b64: str):
            self._secret_key = base64.b64decode(private_key_b64)
            self._address = algosdk.encoding.encode_address(self._secret_key[32:])

        @property
        def address(self) -> str:
            return self._address

        def sign_transactions(
            self,
            unsigned_txns: list[bytes],
            indexes_to_sign: list[int],
        ) -> list[bytes | None]:
            result = []
            for i, txn_bytes in enumerate(unsigned_txns):
                if i in indexes_to_sign:
                    txn = algosdk.encoding.msgpack_decode(txn_bytes)
                    signed = txn.sign(self._secret_key)
                    result.append(algosdk.encoding.msgpack_encode(signed))
                else:
                    result.append(None)
            return result

    signer = MyAlgorandSigner(os.environ["AVM_PRIVATE_KEY"])
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

# Signer protocols (implementations provided by integrator using algosdk)
from .signer import (
    ClientAvmSigner,
    FacilitatorAvmSigner,
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
    # Signer protocols (implementations provided by integrator)
    "ClientAvmSigner",
    "FacilitatorAvmSigner",
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
