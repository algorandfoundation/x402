"""AVM mechanism utility functions.

Provides encoding, decoding, validation, and network utilities
for working with Algorand transactions.
"""

from __future__ import annotations

import base64
import re
from decimal import Decimal
from typing import Any

from .constants import (
    ALGORAND_MAINNET_CAIP2,
    ALGORAND_TESTNET_CAIP2,
    AVM_ADDRESS_REGEX,
    BLOCKED_TXN_TYPES,
    DEFAULT_DECIMALS,
    GENESIS_HASH_TO_NETWORK,
    NETWORK_CONFIGS,
    TXN_TYPE_ASSET_TRANSFER,
    TXN_TYPE_PAYMENT,
    USDC_MAINNET_ASA_ID,
    USDC_TESTNET_ASA_ID,
    V1_TO_V2_NETWORK_MAP,
)
from .types import DecodedTransactionInfo, TransactionGroupInfo

try:
    from algosdk import encoding, transaction
except ImportError as e:
    raise ImportError(
        "AVM mechanism requires py-algorand-sdk. Install with: pip install x402[avm]"
    ) from e


def is_valid_address(address: str) -> bool:
    """Validate an Algorand address format.

    Args:
        address: String to validate.

    Returns:
        True if valid Algorand address format.
    """
    if not address or not isinstance(address, str):
        return False

    if not re.match(AVM_ADDRESS_REGEX, address):
        return False

    try:
        encoding.decode_address(address)
        return True
    except Exception:
        return False


def normalize_network(network: str) -> str:
    """Normalize network identifier to CAIP-2 format.

    Args:
        network: Network identifier (V1 name or CAIP-2).

    Returns:
        CAIP-2 network identifier.

    Raises:
        ValueError: If network is not supported.
    """
    # Already CAIP-2 format
    if network.startswith("algorand:"):
        if network in NETWORK_CONFIGS:
            return network
        raise ValueError(f"Unsupported CAIP-2 network: {network}")

    # V1 name
    if network in V1_TO_V2_NETWORK_MAP:
        return V1_TO_V2_NETWORK_MAP[network]

    raise ValueError(f"Unsupported network: {network}")


def is_valid_network(network: str) -> bool:
    """Check if a network identifier is valid.

    Args:
        network: Network identifier.

    Returns:
        True if network is supported.
    """
    try:
        normalize_network(network)
        return True
    except ValueError:
        return False


def get_network_config(network: str) -> dict[str, Any]:
    """Get configuration for a network.

    Args:
        network: Network identifier (V1 name or CAIP-2).

    Returns:
        NetworkConfig dictionary.

    Raises:
        ValueError: If network is not supported.
    """
    caip2 = normalize_network(network)
    config = NETWORK_CONFIGS.get(caip2)
    if not config:
        raise ValueError(f"Unsupported network: {network}")
    return dict(config)


def get_usdc_asa_id(network: str) -> int:
    """Get the USDC ASA ID for a network.

    Args:
        network: Network identifier.

    Returns:
        USDC ASA ID.

    Raises:
        ValueError: If network is not supported.
    """
    caip2 = normalize_network(network)
    config = NETWORK_CONFIGS.get(caip2)
    if not config:
        raise ValueError(f"Unsupported network: {network}")
    return config["default_asset"]["asa_id"]


def get_genesis_hash(network: str) -> str:
    """Get the genesis hash for a network.

    Args:
        network: Network identifier.

    Returns:
        Base64-encoded genesis hash.

    Raises:
        ValueError: If network is not supported.
    """
    config = get_network_config(network)
    return config["genesis_hash"]


def network_from_genesis_hash(genesis_hash: str) -> str | None:
    """Determine CAIP-2 network from genesis hash.

    Args:
        genesis_hash: Base64-encoded genesis hash.

    Returns:
        CAIP-2 network identifier or None if unknown.
    """
    return GENESIS_HASH_TO_NETWORK.get(genesis_hash)


def parse_money_to_decimal(money: str | float | int) -> float:
    """Parse money value to decimal.

    Args:
        money: Money value (string, float, or int).

    Returns:
        Decimal amount.
    """
    if isinstance(money, str):
        # Remove currency symbols and whitespace
        cleaned = money.strip().lstrip("$").replace(",", "")
        return float(Decimal(cleaned))
    return float(money)


def to_atomic_amount(amount: float, decimals: int = DEFAULT_DECIMALS) -> int:
    """Convert decimal amount to atomic units.

    Args:
        amount: Decimal amount.
        decimals: Number of decimal places.

    Returns:
        Amount in atomic units (smallest unit).
    """
    return int(Decimal(str(amount)) * Decimal(10**decimals))


def from_atomic_amount(amount: int, decimals: int = DEFAULT_DECIMALS) -> float:
    """Convert atomic units to decimal amount.

    Args:
        amount: Amount in atomic units.
        decimals: Number of decimal places.

    Returns:
        Decimal amount.
    """
    return float(Decimal(amount) / Decimal(10**decimals))


def decode_transaction_bytes(txn_bytes: bytes) -> DecodedTransactionInfo:
    """Decode transaction bytes to DecodedTransactionInfo.

    Handles both signed and unsigned transactions.

    Args:
        txn_bytes: Msgpack-encoded transaction bytes.

    Returns:
        DecodedTransactionInfo with extracted data.

    Raises:
        ValueError: If decoding fails.
    """
    try:
        # Note: msgpack_decode expects a base64 string, so encode the raw bytes
        b64_encoded = base64.b64encode(txn_bytes).decode("utf-8")
        decoded = encoding.msgpack_decode(b64_encoded)
    except Exception as e:
        raise ValueError(f"Failed to decode transaction: {e}") from e

    # Determine if signed or unsigned
    is_signed = False
    txn_dict: dict[str, Any]

    if isinstance(decoded, dict):
        if "txn" in decoded:
            # Signed transaction format: {"sig": ..., "txn": {...}}
            is_signed = "sig" in decoded or "msig" in decoded or "lsig" in decoded
            txn_dict = decoded["txn"]
        else:
            # Unsigned transaction format
            txn_dict = decoded
    elif isinstance(decoded, transaction.SignedTransaction):
        is_signed = decoded.signature is not None
        txn_dict = decoded.dictify()["txn"]
    elif isinstance(decoded, transaction.Transaction):
        txn_dict = decoded.dictify()
    else:
        raise ValueError(f"Unknown transaction format: {type(decoded)}")

    # Extract common fields
    txn_type = txn_dict.get("type", "unknown")
    sender_bytes = txn_dict.get("snd", b"")
    sender = encoding.encode_address(sender_bytes) if sender_bytes else ""
    fee = txn_dict.get("fee", 0)
    first_valid = txn_dict.get("fv", 0)
    last_valid = txn_dict.get("lv", 0)

    # Genesis hash
    gh_bytes = txn_dict.get("gh", b"")
    genesis_hash = base64.b64encode(gh_bytes).decode("utf-8") if gh_bytes else ""

    genesis_id = txn_dict.get("gen")

    # Group ID
    group_bytes = txn_dict.get("grp")
    group = base64.b64encode(group_bytes).decode("utf-8") if group_bytes else None

    # Note
    note = txn_dict.get("note")

    # Lease
    lease = txn_dict.get("lx")

    # Rekey-to (SECURITY: should be None)
    rekey_bytes = txn_dict.get("rekey")
    rekey_to = encoding.encode_address(rekey_bytes) if rekey_bytes else None

    # Build base info
    info = DecodedTransactionInfo(
        type=txn_type,
        sender=sender,
        fee=fee,
        first_valid=first_valid,
        last_valid=last_valid,
        genesis_hash=genesis_hash,
        genesis_id=genesis_id,
        group=group,
        is_signed=is_signed,
        note=note,
        lease=lease,
        rekey_to=rekey_to,
    )

    # Extract type-specific fields
    if txn_type == TXN_TYPE_PAYMENT:
        rcv_bytes = txn_dict.get("rcv", b"")
        info.receiver = encoding.encode_address(rcv_bytes) if rcv_bytes else None
        info.amount = txn_dict.get("amt", 0)
        close_bytes = txn_dict.get("close")
        info.close_remainder_to = (
            encoding.encode_address(close_bytes) if close_bytes else None
        )

    elif txn_type == TXN_TYPE_ASSET_TRANSFER:
        info.asset_index = txn_dict.get("xaid", 0)
        arcv_bytes = txn_dict.get("arcv", b"")
        info.asset_receiver = encoding.encode_address(arcv_bytes) if arcv_bytes else None
        info.asset_amount = txn_dict.get("aamt", 0)
        aclose_bytes = txn_dict.get("aclose")
        info.asset_close_to = (
            encoding.encode_address(aclose_bytes) if aclose_bytes else None
        )

    return info


def decode_base64_transaction(b64_txn: str) -> DecodedTransactionInfo:
    """Decode a base64-encoded transaction.

    Args:
        b64_txn: Base64-encoded msgpack transaction.

    Returns:
        DecodedTransactionInfo with extracted data.

    Raises:
        ValueError: If decoding fails.
    """
    try:
        txn_bytes = base64.b64decode(b64_txn)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    return decode_transaction_bytes(txn_bytes)


def decode_payment_group(
    payment_group: list[str],
    payment_index: int,
) -> TransactionGroupInfo:
    """Decode a payment group from base64 strings.

    Args:
        payment_group: List of base64-encoded transactions.
        payment_index: Index of the payment transaction.

    Returns:
        TransactionGroupInfo with all decoded transactions.

    Raises:
        ValueError: If decoding fails.
    """
    transactions: list[DecodedTransactionInfo] = []
    total_fee = 0
    group_id: str | None = None
    has_fee_payer = False
    fee_payer_index: int | None = None

    for i, b64_txn in enumerate(payment_group):
        txn_info = decode_base64_transaction(b64_txn)
        transactions.append(txn_info)
        total_fee += txn_info.fee

        # Capture group ID from first transaction
        if i == 0 and txn_info.group:
            group_id = txn_info.group

        # Detect fee payer transaction (self-payment with no amount)
        if (
            txn_info.type == TXN_TYPE_PAYMENT
            and txn_info.receiver == txn_info.sender
            and (txn_info.amount == 0 or txn_info.amount is None)
        ):
            has_fee_payer = True
            fee_payer_index = i

    return TransactionGroupInfo(
        transactions=transactions,
        group_id=group_id,
        total_fee=total_fee,
        has_fee_payer=has_fee_payer,
        fee_payer_index=fee_payer_index,
        payment_index=payment_index,
    )


def is_blocked_transaction_type(txn_type: str) -> bool:
    """Check if a transaction type is blocked for security.

    Args:
        txn_type: Transaction type string.

    Returns:
        True if the transaction type is blocked.
    """
    return txn_type in BLOCKED_TXN_TYPES


def validate_no_security_risks(txn_info: DecodedTransactionInfo) -> str | None:
    """Validate that a transaction has no security risks.

    Checks for:
    - Rekey operations
    - Close-to operations (draining accounts)
    - Blocked transaction types (keyreg)

    Args:
        txn_info: Decoded transaction info.

    Returns:
        Error code string if security risk found, None otherwise.
    """
    from .constants import (
        ERR_BLOCKED_TXN_TYPE,
        ERR_CLOSE_TO_DETECTED,
        ERR_REKEY_DETECTED,
    )

    # Check for rekey
    if txn_info.rekey_to:
        return ERR_REKEY_DETECTED

    # Check for close-to
    if txn_info.type == TXN_TYPE_PAYMENT and txn_info.close_remainder_to:
        return ERR_CLOSE_TO_DETECTED

    if txn_info.type == TXN_TYPE_ASSET_TRANSFER and txn_info.asset_close_to:
        return ERR_CLOSE_TO_DETECTED

    # Check for blocked types
    if is_blocked_transaction_type(txn_info.type):
        return ERR_BLOCKED_TXN_TYPE

    return None


def validate_fee_payer_transaction(
    txn_info: DecodedTransactionInfo,
    expected_fee_payer: str,
) -> str | None:
    """Validate a fee payer transaction.

    Per spec, fee payer transaction must be:
    - Type "pay" (payment)
    - Sender is the fee payer
    - Receiver is the fee payer (self-payment)
    - Amount is 0 (no value transfer)
    - No close-to field
    - No rekey field
    - Fee is reasonable (covers pooled fees)

    Args:
        txn_info: Decoded transaction info.
        expected_fee_payer: Expected fee payer address.

    Returns:
        Error code string if invalid, None otherwise.
    """
    from .constants import (
        ERR_FEE_PAYER_HAS_AMOUNT,
        ERR_FEE_PAYER_HAS_CLOSE,
        ERR_FEE_PAYER_HAS_REKEY,
        ERR_FEE_PAYER_INVALID_TXN,
    )

    # Must be payment type
    if txn_info.type != TXN_TYPE_PAYMENT:
        return ERR_FEE_PAYER_INVALID_TXN

    # Sender must be fee payer
    if txn_info.sender != expected_fee_payer:
        return ERR_FEE_PAYER_INVALID_TXN

    # Receiver must be fee payer (self-payment)
    if txn_info.receiver != expected_fee_payer:
        return ERR_FEE_PAYER_INVALID_TXN

    # Amount must be 0
    if txn_info.amount and txn_info.amount > 0:
        return ERR_FEE_PAYER_HAS_AMOUNT

    # No close-to
    if txn_info.close_remainder_to:
        return ERR_FEE_PAYER_HAS_CLOSE

    # No rekey
    if txn_info.rekey_to:
        return ERR_FEE_PAYER_HAS_REKEY

    return None


def encode_transaction_group(
    txn_bytes_list: list[bytes],
) -> list[str]:
    """Encode a list of transaction bytes to base64 strings.

    Args:
        txn_bytes_list: List of msgpack-encoded transaction bytes.

    Returns:
        List of base64-encoded strings.
    """
    return [base64.b64encode(txn_bytes).decode("utf-8") for txn_bytes in txn_bytes_list]


def get_default_usdc_info(network: str) -> dict[str, Any]:
    """Get default USDC asset info for a network.

    Args:
        network: Network identifier.

    Returns:
        Asset info dictionary with asa_id, name, decimals.
    """
    caip2 = normalize_network(network)

    if caip2 == ALGORAND_MAINNET_CAIP2:
        return {
            "asa_id": USDC_MAINNET_ASA_ID,
            "name": "USDC",
            "decimals": DEFAULT_DECIMALS,
        }
    elif caip2 == ALGORAND_TESTNET_CAIP2:
        return {
            "asa_id": USDC_TESTNET_ASA_ID,
            "name": "USDC",
            "decimals": DEFAULT_DECIMALS,
        }
    else:
        raise ValueError(f"Unknown network: {network}")
