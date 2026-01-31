"""AVM signer protocol definitions.

Defines the abstract interfaces for signing operations:
- ClientAvmSigner: Used by x402Client for creating payment payloads.
- FacilitatorAvmSigner: Used by x402Facilitator for verification/settlement.
"""

from typing import Protocol


class ClientAvmSigner(Protocol):
    """Protocol for AVM client-side signing operations.

    Used by x402Client to sign transactions for payment payloads.

    The client signer is responsible for:
    - Providing the sender address
    - Signing transactions where the client is the sender
    """

    @property
    def address(self) -> str:
        """Get the signer's Algorand address.

        Returns:
            58-character Algorand address.
        """
        ...

    def sign_transactions(
        self,
        unsigned_txns: list[bytes],
        indexes_to_sign: list[int],
    ) -> list[bytes | None]:
        """Sign specified transactions in a group.

        Only signs transactions at the specified indexes.
        Returns None for transactions that should not be signed by this signer.

        Args:
            unsigned_txns: List of unsigned transaction bytes (msgpack encoded).
            indexes_to_sign: Indexes of transactions this signer should sign.

        Returns:
            List parallel to unsigned_txns, with signed transaction bytes
            at indexes_to_sign and None elsewhere.
        """
        ...


class FacilitatorAvmSigner(Protocol):
    """Protocol for AVM facilitator-side signing operations.

    Used by x402Facilitator to verify, sign, simulate, and settle transactions.

    The facilitator signer is responsible for:
    - Providing the fee payer addresses it manages
    - Signing fee payer transactions
    - Simulating transaction groups
    - Sending transaction groups to the network
    - Confirming transaction finality
    """

    def get_addresses(self) -> list[str]:
        """Get all managed fee payer addresses.

        Returns:
            List of 58-character Algorand addresses that can be used
            as fee payers. Enables load distribution across multiple signers.
        """
        ...

    def sign_transaction(
        self,
        txn_bytes: bytes,
        fee_payer: str,
        network: str,
    ) -> bytes:
        """Sign a single transaction with the fee payer's key.

        Args:
            txn_bytes: Unsigned transaction bytes (msgpack encoded).
            fee_payer: Algorand address of the fee payer.
            network: CAIP-2 network identifier.

        Returns:
            Signed transaction bytes (msgpack encoded).

        Raises:
            ValueError: If fee_payer is not managed by this signer.
        """
        ...

    def sign_group(
        self,
        group_bytes: list[bytes],
        fee_payer: str,
        indexes_to_sign: list[int],
        network: str,
    ) -> list[bytes]:
        """Sign specified transactions in a group with the fee payer's key.

        Args:
            group_bytes: List of transaction bytes (some signed, some unsigned).
            fee_payer: Algorand address of the fee payer.
            indexes_to_sign: Indexes of transactions the fee payer should sign.
            network: CAIP-2 network identifier.

        Returns:
            List of transaction bytes with fee payer's transactions now signed.

        Raises:
            ValueError: If fee_payer is not managed by this signer.
        """
        ...

    def simulate_group(
        self,
        group_bytes: list[bytes],
        network: str,
    ) -> None:
        """Simulate a transaction group to verify it will succeed.

        Uses Algorand's simulate endpoint to dry-run the transaction group
        without committing it to the network.

        Args:
            group_bytes: List of signed/unsigned transaction bytes.
            network: CAIP-2 network identifier.

        Raises:
            Exception: If simulation fails (contains error message).
        """
        ...

    def send_group(
        self,
        group_bytes: list[bytes],
        network: str,
    ) -> str:
        """Send a transaction group to the network.

        Args:
            group_bytes: List of fully-signed transaction bytes.
            network: CAIP-2 network identifier.

        Returns:
            Transaction ID of the first transaction in the group.

        Raises:
            Exception: If sending fails.
        """
        ...

    def confirm_transaction(
        self,
        txid: str,
        network: str,
        rounds: int = 4,
    ) -> None:
        """Wait for transaction confirmation.

        Algorand has instant finality - once a transaction is in a block,
        it is final and will never be reverted.

        Args:
            txid: Transaction ID to confirm.
            network: CAIP-2 network identifier.
            rounds: Maximum rounds to wait (default 4).

        Raises:
            Exception: If confirmation times out or transaction fails.
        """
        ...
