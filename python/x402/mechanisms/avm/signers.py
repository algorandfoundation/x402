"""Concrete signer implementations for AVM mechanism.

Provides ready-to-use implementations of ClientAvmSigner and FacilitatorAvmSigner
using py-algorand-sdk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from algosdk import account, encoding, transaction
    from algosdk.v2client import algod
    from algosdk.v2client.models import SimulateRequest, SimulateRequestTransactionGroup

    ALGOSDK_AVAILABLE = True
except ImportError:
    ALGOSDK_AVAILABLE = False

from .constants import NETWORK_CONFIGS
from .utils import normalize_network

if TYPE_CHECKING:
    pass


def _check_algosdk() -> None:
    """Check that algosdk is available."""
    if not ALGOSDK_AVAILABLE:
        raise ImportError(
            "AVM mechanism requires py-algorand-sdk. Install with: pip install x402[avm]"
        )


class AlgorandSigner:
    """Simple client-side signer using a private key.

    Implements ClientAvmSigner protocol.

    Example:
        ```python
        signer = AlgorandSigner.from_mnemonic("word1 word2 ... word25")
        client = x402Client()
        client.register("algorand:*", ExactAvmScheme(signer))
        ```
    """

    def __init__(self, private_key: str):
        """Create signer from private key.

        Args:
            private_key: Base64-encoded Algorand private key.
        """
        _check_algosdk()
        self._private_key = private_key
        self._address = account.address_from_private_key(private_key)

    @classmethod
    def from_mnemonic(cls, mnemonic: str) -> "AlgorandSigner":
        """Create signer from 25-word mnemonic.

        Args:
            mnemonic: 25-word Algorand mnemonic phrase.

        Returns:
            AlgorandSigner instance.
        """
        _check_algosdk()
        from algosdk import mnemonic as mn

        private_key = mn.to_private_key(mnemonic)
        return cls(private_key)

    @classmethod
    def generate(cls) -> tuple["AlgorandSigner", str]:
        """Generate a new random signer.

        Returns:
            Tuple of (signer, mnemonic).
        """
        _check_algosdk()
        from algosdk import mnemonic as mn

        private_key, address = account.generate_account()
        mnemonic = mn.from_private_key(private_key)
        return cls(private_key), mnemonic

    @property
    def address(self) -> str:
        """Get the signer's Algorand address."""
        return self._address

    def sign_transactions(
        self,
        unsigned_txns: list[bytes],
        indexes_to_sign: list[int],
    ) -> list[bytes | None]:
        """Sign specified transactions in a group.

        Args:
            unsigned_txns: List of unsigned transaction bytes.
            indexes_to_sign: Indexes to sign.

        Returns:
            List with signed bytes at specified indexes, None elsewhere.
        """
        results: list[bytes | None] = [None] * len(unsigned_txns)

        for idx in indexes_to_sign:
            if idx >= len(unsigned_txns):
                continue

            # Decode the unsigned transaction
            txn_dict = encoding.msgpack_decode(unsigned_txns[idx])
            txn = transaction.Transaction.undictify(txn_dict)

            # Sign it
            signed_txn = txn.sign(self._private_key)

            # Encode the signed transaction
            results[idx] = encoding.msgpack_encode(signed_txn)

        return results


class FacilitatorAlgorandSigner:
    """Facilitator-side signer managing one or more fee payer accounts.

    Implements FacilitatorAvmSigner protocol.

    Example:
        ```python
        signer = FacilitatorAlgorandSigner()
        signer.add_account(private_key_1)
        signer.add_account(private_key_2)
        facilitator = x402Facilitator()
        facilitator.register([ALGORAND_MAINNET_CAIP2], ExactAvmScheme(signer))
        ```
    """

    def __init__(self, algod_url: str | None = None, algod_token: str = ""):
        """Create facilitator signer.

        Args:
            algod_url: Custom Algod URL (optional).
            algod_token: Algod API token (optional).
        """
        _check_algosdk()
        self._custom_algod_url = algod_url
        self._algod_token = algod_token
        self._accounts: dict[str, str] = {}  # address -> private_key
        self._clients: dict[str, algod.AlgodClient] = {}

    def add_account(self, private_key: str) -> "FacilitatorAlgorandSigner":
        """Add a fee payer account.

        Args:
            private_key: Base64-encoded Algorand private key.

        Returns:
            Self for chaining.
        """
        address = account.address_from_private_key(private_key)
        self._accounts[address] = private_key
        return self

    def add_account_from_mnemonic(self, mnemonic: str) -> "FacilitatorAlgorandSigner":
        """Add a fee payer account from mnemonic.

        Args:
            mnemonic: 25-word Algorand mnemonic phrase.

        Returns:
            Self for chaining.
        """
        from algosdk import mnemonic as mn

        private_key = mn.to_private_key(mnemonic)
        return self.add_account(private_key)

    def get_addresses(self) -> list[str]:
        """Get all managed fee payer addresses."""
        return list(self._accounts.keys())

    def _get_client(self, network: str) -> algod.AlgodClient:
        """Get or create Algod client for network."""
        caip2_network = normalize_network(network)

        if caip2_network in self._clients:
            return self._clients[caip2_network]

        if self._custom_algod_url:
            algod_url = self._custom_algod_url
        else:
            config = NETWORK_CONFIGS.get(caip2_network)
            if not config:
                raise ValueError(f"Unsupported network: {network}")
            algod_url = config["algod_url"]

        client = algod.AlgodClient(self._algod_token, algod_url)
        self._clients[caip2_network] = client
        return client

    def _get_private_key(self, fee_payer: str) -> str:
        """Get private key for fee payer address."""
        if fee_payer not in self._accounts:
            raise ValueError(
                f"Fee payer {fee_payer} not managed by this signer. "
                f"Available: {list(self._accounts.keys())}"
            )
        return self._accounts[fee_payer]

    def sign_transaction(
        self,
        txn_bytes: bytes,
        fee_payer: str,
        network: str,
    ) -> bytes:
        """Sign a single transaction with the fee payer's key."""
        _ = network  # Unused, network validated elsewhere
        private_key = self._get_private_key(fee_payer)

        # Decode the unsigned transaction
        txn_dict = encoding.msgpack_decode(txn_bytes)
        txn = transaction.Transaction.undictify(txn_dict)

        # Sign it
        signed_txn = txn.sign(private_key)

        # Encode the signed transaction
        return encoding.msgpack_encode(signed_txn)

    def sign_group(
        self,
        group_bytes: list[bytes],
        fee_payer: str,
        indexes_to_sign: list[int],
        network: str,
    ) -> list[bytes]:
        """Sign specified transactions in a group with the fee payer's key."""
        _ = network  # Unused, network validated elsewhere
        private_key = self._get_private_key(fee_payer)

        results: list[bytes] = list(group_bytes)

        for idx in indexes_to_sign:
            if idx >= len(group_bytes):
                continue

            # Decode the unsigned transaction
            decoded = encoding.msgpack_decode(group_bytes[idx])

            # Check if it's already a signed transaction
            if isinstance(decoded, dict) and "txn" in decoded:
                # Already signed, extract the inner transaction
                txn_dict = decoded["txn"]
            else:
                txn_dict = decoded

            txn = transaction.Transaction.undictify(txn_dict)

            # Sign it
            signed_txn = txn.sign(private_key)

            # Encode the signed transaction
            results[idx] = encoding.msgpack_encode(signed_txn)

        return results

    def simulate_group(
        self,
        group_bytes: list[bytes],
        network: str,
    ) -> None:
        """Simulate a transaction group."""
        client = self._get_client(network)

        # Decode all transactions in the group
        signed_txns = []
        for txn_bytes in group_bytes:
            decoded = encoding.msgpack_decode(txn_bytes)
            if isinstance(decoded, transaction.SignedTransaction):
                signed_txns.append(decoded)
            elif isinstance(decoded, dict):
                if "sig" in decoded or "msig" in decoded or "lsig" in decoded:
                    # It's a signed transaction dict
                    signed_txns.append(
                        transaction.SignedTransaction.undictify(decoded)
                    )
                else:
                    # Unsigned - wrap in a SignedTransaction with empty signature
                    txn = transaction.Transaction.undictify(decoded.get("txn", decoded))
                    signed_txns.append(
                        transaction.SignedTransaction(txn, signature=None)
                    )
            else:
                raise ValueError(f"Unknown transaction format at index {len(signed_txns)}")

        # Build simulate request
        simulate_request = SimulateRequest(
            txn_groups=[
                SimulateRequestTransactionGroup(txns=signed_txns)
            ],
            allow_empty_signatures=True,
        )

        # Run simulation
        result = client.simulate_transactions(simulate_request)

        # Check for failures
        if result.get("txn-groups"):
            for group in result["txn-groups"]:
                if group.get("failure-message"):
                    raise Exception(f"Simulation failed: {group['failure-message']}")
                for txn_result in group.get("txn-results", []):
                    if txn_result.get("failure-message"):
                        raise Exception(f"Simulation failed: {txn_result['failure-message']}")

    def send_group(
        self,
        group_bytes: list[bytes],
        network: str,
    ) -> str:
        """Send a transaction group to the network."""
        client = self._get_client(network)

        # Decode all transactions
        signed_txns = []
        for txn_bytes in group_bytes:
            decoded = encoding.msgpack_decode(txn_bytes)
            if isinstance(decoded, transaction.SignedTransaction):
                signed_txns.append(decoded)
            elif isinstance(decoded, dict):
                signed_txns.append(
                    transaction.SignedTransaction.undictify(decoded)
                )
            else:
                raise ValueError("Transaction must be signed before sending")

        # Send the group
        txid = client.send_transactions(signed_txns)
        return txid

    def confirm_transaction(
        self,
        txid: str,
        network: str,
        rounds: int = 4,
    ) -> None:
        """Wait for transaction confirmation."""
        client = self._get_client(network)
        transaction.wait_for_confirmation(client, txid, rounds)
