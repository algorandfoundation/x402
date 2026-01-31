"""AVM mechanism types - dataclasses for payloads and transaction info."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExactAvmPayload:
    """Exact payment payload for AVM networks.

    Contains an atomic group of base64-encoded msgpack transactions.
    The paymentIndex identifies which transaction pays the resource server.

    Attributes:
        payment_group: List of base64-encoded msgpack transactions.
        payment_index: Index of the payment transaction in the group.
    """

    payment_group: list[str] = field(default_factory=list)
    payment_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with camelCase keys for JSON.
        """
        return {
            "paymentGroup": self.payment_group,
            "paymentIndex": self.payment_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExactAvmPayload":
        """Create from dictionary.

        Args:
            data: Dictionary with payload data.

        Returns:
            ExactAvmPayload instance.
        """
        return cls(
            payment_group=data.get("paymentGroup", []),
            payment_index=data.get("paymentIndex", 0),
        )


# Type aliases for V1/V2 compatibility
ExactAvmPayloadV1 = ExactAvmPayload
ExactAvmPayloadV2 = ExactAvmPayload


@dataclass
class DecodedTransactionInfo:
    """Information extracted from a decoded Algorand transaction.

    Provides a unified view of transaction data regardless of whether
    the transaction is signed or unsigned.

    Attributes:
        type: Transaction type ("pay", "axfer", "keyreg", etc.).
        sender: Algorand address of the sender.
        fee: Fee in microalgos.
        first_valid: First valid round.
        last_valid: Last valid round.
        genesis_hash: Base64 encoded genesis hash.
        genesis_id: Genesis ID string (e.g., "mainnet-v1.0").
        group: Base64 encoded group ID or None.
        is_signed: Whether the transaction has a signature.
        note: Transaction note bytes or None.

        # Payment-specific (type == "pay")
        receiver: Payment receiver address or None.
        amount: Payment amount in microalgos or None.
        close_remainder_to: Close-to address or None.

        # Asset transfer-specific (type == "axfer")
        asset_index: ASA ID or None.
        asset_receiver: Asset receiver address or None.
        asset_amount: Asset amount or None.
        asset_close_to: Asset close-to address or None.

        # Security fields
        rekey_to: Rekey-to address or None (SECURITY: should be None).
    """

    type: str
    sender: str
    fee: int
    first_valid: int
    last_valid: int
    genesis_hash: str
    genesis_id: str | None = None
    group: str | None = None
    is_signed: bool = False
    note: bytes | None = None

    # Payment-specific (type == "pay")
    receiver: str | None = None
    amount: int | None = None
    close_remainder_to: str | None = None

    # Asset transfer-specific (type == "axfer")
    asset_index: int | None = None
    asset_receiver: str | None = None
    asset_amount: int | None = None
    asset_close_to: str | None = None

    # Security fields
    rekey_to: str | None = None


@dataclass
class TransactionGroupInfo:
    """Information about a decoded transaction group.

    Provides summary information about a group of transactions.

    Attributes:
        transactions: List of decoded transaction info.
        group_id: Base64 encoded group ID (if present).
        total_fee: Sum of all transaction fees.
        has_fee_payer: Whether a fee payer transaction exists.
        fee_payer_index: Index of the fee payer transaction or None.
        payment_index: Index of the payment transaction.
    """

    transactions: list[DecodedTransactionInfo]
    group_id: str | None = None
    total_fee: int = 0
    has_fee_payer: bool = False
    fee_payer_index: int | None = None
    payment_index: int = 0
