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
    from .bip32_ed25519 import ExtendedKey


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
        # From 25-word Algorand mnemonic
        signer = AlgorandSigner.from_mnemonic("word1 word2 ... word25")

        # From 24-word BIP-39 mnemonic (Pera, Defly compatible)
        signer = AlgorandSigner.from_mnemonic("word1 word2 ... word24")

        client = x402Client()
        client.register("algorand:*", ExactAvmScheme(signer))
        ```
    """

    def __init__(self, private_key: str, extended_key: str | None = None):
        """Create signer from private key.

        Args:
            private_key: Base64-encoded Algorand private key.
            extended_key: Optional base64-encoded extended key (kL || kR) for BIP32-Ed25519.
        """
        _check_algosdk()
        self._private_key = private_key
        self._extended_key = extended_key
        self._address = account.address_from_private_key(private_key)

    @classmethod
    def from_mnemonic(cls, mnemonic: str, account_index: int = 0) -> "AlgorandSigner":
        """Create signer from mnemonic phrase.

        Supports both 24-word BIP-39 mnemonics and 25-word Algorand native mnemonics.
        BIP-39 mnemonics use BIP32-Ed25519 derivation, compatible with wallets
        like Lute, Pera, Defly, and other BIP-39 compatible Algorand wallets.

        Args:
            mnemonic: 24-word BIP-39 or 25-word Algorand mnemonic phrase.
            account_index: Account index for BIP-39 derivation (ignored for 25-word).

        Returns:
            AlgorandSigner instance.

        Raises:
            ValueError: If mnemonic is invalid.
            ImportError: If bip_utils is not installed (for 24-word mnemonics).
        """
        _check_algosdk()
        from .mnemonic import mnemonic_to_algorand_account

        algo_account = mnemonic_to_algorand_account(mnemonic, account_index)
        return cls(algo_account.private_key, algo_account.extended_key)

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
        import base64

        results: list[bytes | None] = [None] * len(unsigned_txns)

        for idx in indexes_to_sign:
            if idx >= len(unsigned_txns):
                continue

            # Decode the unsigned transaction
            # Note: msgpack_decode expects base64 string, so convert bytes to b64
            b64_input = base64.b64encode(unsigned_txns[idx]).decode("utf-8")
            decoded = encoding.msgpack_decode(b64_input)

            # Handle both dict and Transaction object returns from msgpack_decode
            if isinstance(decoded, transaction.Transaction):
                txn = decoded
            elif isinstance(decoded, dict):
                txn = transaction.Transaction.undictify(decoded)
            else:
                raise TypeError(f"Unexpected decoded type: {type(decoded)}")

            # Sign it - use extended key for BIP32-Ed25519 derived keys
            if self._extended_key:
                signed_txn = self._sign_with_extended_key(txn)
            else:
                signed_txn = txn.sign(self._private_key)

            # Encode the signed transaction
            # Note: msgpack_encode returns a base64 string, convert to bytes
            encoded = encoding.msgpack_encode(signed_txn)
            results[idx] = base64.b64decode(encoded)

        return results

    def _sign_with_extended_key(
        self,
        txn: transaction.Transaction,
    ) -> transaction.SignedTransaction:
        """Sign a transaction using BIP32-Ed25519 extended key.

        Args:
            txn: The transaction to sign.

        Returns:
            SignedTransaction with the proper signature.
        """
        import base64

        from nacl.bindings import crypto_scalarmult_ed25519_base_noclamp
        from nacl.signing import VerifyKey

        from .bip32_ed25519 import ExtendedKey, sign_with_extended_key

        # Get the extended key (kL || kR)
        # Ensure proper base64 padding
        extended_key_b64 = self._extended_key
        padding_needed = (4 - len(extended_key_b64) % 4) % 4
        extended_key_b64_padded = extended_key_b64 + "=" * padding_needed
        extended_key_bytes = base64.b64decode(extended_key_b64_padded)

        if len(extended_key_bytes) != 64:
            raise ValueError(
                f"Extended key should be 64 bytes, got {len(extended_key_bytes)}"
            )

        kL = extended_key_bytes[:32]
        kR = extended_key_bytes[32:64]

        # Create ExtendedKey (chain code not needed for signing)
        dummy_chain_code = bytes(32)
        extended_key = ExtendedKey(kL=kL, kR=kR, chain_code=dummy_chain_code)

        # Get the bytes to sign: "TX" + msgpack(transaction)
        txn_msgpack_b64 = encoding.msgpack_encode(txn)
        # Ensure proper base64 padding for msgpack output
        padding_needed = (4 - len(txn_msgpack_b64) % 4) % 4
        txn_msgpack_b64_padded = txn_msgpack_b64 + "=" * padding_needed
        txn_bytes = b"TX" + base64.b64decode(txn_msgpack_b64_padded)

        # Sign with the extended key
        signature = sign_with_extended_key(extended_key, txn_bytes)

        # Verify signature length
        if len(signature) != 64:
            raise ValueError(f"Signature should be 64 bytes, got {len(signature)}")

        # Verify the signature locally before returning
        public_key = crypto_scalarmult_ed25519_base_noclamp(kL)
        verify_key = VerifyKey(public_key)
        try:
            verify_key.verify(txn_bytes, signature)
        except Exception as e:
            raise ValueError(f"Local signature verification failed: {e}")

        # Create SignedTransaction with the signature
        # NOTE: algosdk expects signature as base64-encoded string, not raw bytes
        sig_b64 = base64.b64encode(signature).decode("utf-8")
        return transaction.SignedTransaction(txn, signature=sig_b64)


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
        self._extended_keys: dict[str, str] = {}  # address -> extended_key (for BIP32-Ed25519)
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

    def add_account_from_mnemonic(
        self, mnemonic: str, account_index: int = 0
    ) -> "FacilitatorAlgorandSigner":
        """Add a fee payer account from mnemonic.

        Supports both 24-word BIP-39 mnemonics and 25-word Algorand native mnemonics.
        BIP-39 mnemonics use BIP32-Ed25519 derivation, compatible with wallets
        like Lute, Pera, Defly, and other BIP-39 compatible Algorand wallets.

        Args:
            mnemonic: 24-word BIP-39 or 25-word Algorand mnemonic phrase.
            account_index: Account index for BIP-39 derivation (ignored for 25-word).

        Returns:
            Self for chaining.

        Raises:
            ValueError: If mnemonic is invalid.
            ImportError: If bip_utils is not installed (for 24-word mnemonics).
        """
        from .mnemonic import mnemonic_to_algorand_account

        algo_account = mnemonic_to_algorand_account(mnemonic, account_index)
        self.add_account(algo_account.private_key)

        # Store extended key for BIP32-Ed25519 derived keys (needed for proper signing)
        if algo_account.extended_key:
            self._extended_keys[algo_account.address] = algo_account.extended_key

        return self

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

    def _sign_with_extended_key(
        self,
        txn: transaction.Transaction,
        address: str,
    ) -> transaction.SignedTransaction:
        """Sign a transaction using BIP32-Ed25519 extended key.

        This is required for BIP-39 derived keys because algosdk's standard
        signing re-hashes the key, which produces wrong signatures for
        BIP32-Ed25519 derived scalars.

        Args:
            txn: The transaction to sign.
            address: The address whose extended key to use.

        Returns:
            SignedTransaction with the proper signature.
        """
        import base64

        from nacl.bindings import crypto_scalarmult_ed25519_base_noclamp
        from nacl.signing import VerifyKey

        from .bip32_ed25519 import ExtendedKey, sign_with_extended_key

        # Get the extended key (kL || kR)
        extended_key_b64 = self._extended_keys[address]
        # Ensure proper base64 padding
        padding_needed = (4 - len(extended_key_b64) % 4) % 4
        extended_key_b64_padded = extended_key_b64 + "=" * padding_needed
        extended_key_bytes = base64.b64decode(extended_key_b64_padded)

        if len(extended_key_bytes) != 64:
            raise ValueError(
                f"Extended key should be 64 bytes, got {len(extended_key_bytes)}"
            )

        kL = extended_key_bytes[:32]
        kR = extended_key_bytes[32:64]

        # We need the chain code for ExtendedKey, but for signing we only need kL and kR
        # Create a dummy chain code since it's not used in signing
        dummy_chain_code = bytes(32)
        extended_key = ExtendedKey(kL=kL, kR=kR, chain_code=dummy_chain_code)

        # Get the bytes to sign: "TX" + msgpack(transaction)
        # msgpack_encode returns base64 string, need raw bytes
        txn_msgpack_b64 = encoding.msgpack_encode(txn)
        # Ensure proper base64 padding for msgpack output
        padding_needed = (4 - len(txn_msgpack_b64) % 4) % 4
        txn_msgpack_b64_padded = txn_msgpack_b64 + "=" * padding_needed
        txn_bytes = b"TX" + base64.b64decode(txn_msgpack_b64_padded)

        # Sign with the extended key
        signature = sign_with_extended_key(extended_key, txn_bytes)

        # Verify signature length
        if len(signature) != 64:
            raise ValueError(f"Signature should be 64 bytes, got {len(signature)}")

        # Verify the signature locally before returning
        public_key = crypto_scalarmult_ed25519_base_noclamp(kL)
        verify_key = VerifyKey(public_key)
        try:
            verify_key.verify(txn_bytes, signature)
        except Exception as e:
            raise ValueError(f"Local signature verification failed: {e}")

        # Create SignedTransaction with the signature
        # NOTE: algosdk expects signature as base64-encoded string, not raw bytes
        sig_b64 = base64.b64encode(signature).decode("utf-8")
        return transaction.SignedTransaction(txn, signature=sig_b64)

    def sign_transaction(
        self,
        txn_bytes: bytes,
        fee_payer: str,
        network: str,
    ) -> bytes:
        """Sign a single transaction with the fee payer's key."""
        import base64

        _ = network  # Unused, network validated elsewhere
        private_key = self._get_private_key(fee_payer)

        # Decode the unsigned transaction (convert bytes to b64 for msgpack_decode)
        b64_input = base64.b64encode(txn_bytes).decode("utf-8")
        decoded = encoding.msgpack_decode(b64_input)

        # Handle both dict and Transaction object
        if isinstance(decoded, transaction.Transaction):
            txn = decoded
        elif isinstance(decoded, dict):
            txn = transaction.Transaction.undictify(decoded)
        else:
            raise TypeError(f"Unexpected decoded type: {type(decoded)}")

        # Check if we have an extended key for this address (BIP32-Ed25519 derived)
        if fee_payer in self._extended_keys:
            signed_txn = self._sign_with_extended_key(txn, fee_payer)
        else:
            # Use standard algosdk signing
            signed_txn = txn.sign(private_key)

        # Encode the signed transaction (convert b64 string to bytes)
        encoded = encoding.msgpack_encode(signed_txn)
        return base64.b64decode(encoded)

    def sign_group(
        self,
        group_bytes: list[bytes],
        fee_payer: str,
        indexes_to_sign: list[int],
        network: str,
    ) -> list[bytes]:
        """Sign specified transactions in a group with the fee payer's key."""
        import base64

        _ = network  # Unused, network validated elsewhere
        private_key = self._get_private_key(fee_payer)
        use_extended_key = fee_payer in self._extended_keys

        results: list[bytes] = list(group_bytes)

        for idx in indexes_to_sign:
            if idx >= len(group_bytes):
                continue

            # Decode the unsigned transaction (convert bytes to b64 for msgpack_decode)
            b64_input = base64.b64encode(group_bytes[idx]).decode("utf-8")
            decoded = encoding.msgpack_decode(b64_input)

            # Handle Transaction object or dict
            if isinstance(decoded, transaction.Transaction):
                txn = decoded
            elif isinstance(decoded, transaction.SignedTransaction):
                # Already signed, get the inner transaction
                txn = decoded.transaction
            elif isinstance(decoded, dict):
                # Check if it's already a signed transaction dict
                if "txn" in decoded:
                    # Already signed, extract the inner transaction
                    txn = transaction.Transaction.undictify(decoded["txn"])
                else:
                    txn = transaction.Transaction.undictify(decoded)
            else:
                raise TypeError(f"Unexpected decoded type: {type(decoded)}")

            # Sign it - use extended key for BIP32-Ed25519 derived keys
            if use_extended_key:
                signed_txn = self._sign_with_extended_key(txn, fee_payer)
            else:
                signed_txn = txn.sign(private_key)

            # Encode the signed transaction (convert b64 string to bytes)
            encoded = encoding.msgpack_encode(signed_txn)
            results[idx] = base64.b64decode(encoded)

        return results

    def simulate_group(
        self,
        group_bytes: list[bytes],
        network: str,
    ) -> None:
        """Simulate a transaction group."""
        import base64
        import traceback

        client = self._get_client(network)

        # Decode all transactions in the group
        signed_txns = []
        for idx, txn_bytes in enumerate(group_bytes):
            try:
                # Convert bytes to b64 for msgpack_decode
                b64_input = base64.b64encode(txn_bytes).decode("utf-8")
                decoded = encoding.msgpack_decode(b64_input)
            except Exception as e:
                raise ValueError(
                    f"Transaction {idx}: failed to decode msgpack - {e}\n"
                    f"Input bytes len: {len(txn_bytes)}"
                )
            if isinstance(decoded, transaction.SignedTransaction):
                signed_txns.append(decoded)
            elif isinstance(decoded, transaction.Transaction):
                # Unsigned transaction - wrap in SignedTransaction with empty sig
                signed_txns.append(
                    transaction.SignedTransaction(decoded, signature=None)
                )
            elif isinstance(decoded, dict):
                if "sig" in decoded or "msig" in decoded or "lsig" in decoded:
                    # It's a signed transaction dict
                    sig = decoded.get("sig")
                    if sig is not None:
                        # Validate and normalize signature format
                        if isinstance(sig, bytes):
                            if len(sig) != 64:
                                raise ValueError(
                                    f"Transaction {idx}: signature should be 64 bytes, "
                                    f"got {len(sig)}"
                                )
                            # Signature is already bytes, use as-is
                        elif isinstance(sig, str):
                            # String signature - could be raw binary or base64
                            if len(sig) == 64:
                                # Raw binary string (64 chars = 64 bytes)
                                decoded["sig"] = sig.encode("latin-1")
                            else:
                                # Assume base64 encoded, try to decode
                                try:
                                    padding_needed = (4 - len(sig) % 4) % 4
                                    sig_padded = sig + "=" * padding_needed
                                    decoded["sig"] = base64.b64decode(sig_padded)
                                except Exception as e:
                                    raise ValueError(
                                        f"Transaction {idx}: failed to decode signature "
                                        f"(len={len(sig)}, type=str): {e}"
                                    )
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
                raise ValueError(f"Unknown transaction format at index {idx}")

        # Build simulate request
        # The simulate API expects transactions to be passed as SignedTransaction objects
        # algosdk handles the encoding internally
        simulate_request = SimulateRequest(
            txn_groups=[
                SimulateRequestTransactionGroup(txns=signed_txns)
            ],
            allow_empty_signatures=True,
        )

        # Run simulation
        try:
            result = client.simulate_transactions(simulate_request)
        except Exception as e:
            import traceback
            # Provide more context on simulation errors
            tb = traceback.format_exc()
            raise Exception(
                f"Simulation request failed: {e}\n"
                f"Number of transactions: {len(signed_txns)}\n"
                f"Traceback:\n{tb}"
            )

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
        import base64

        client = self._get_client(network)

        # Decode all transactions
        signed_txns = []
        for txn_bytes in group_bytes:
            # Convert bytes to b64 for msgpack_decode
            b64_input = base64.b64encode(txn_bytes).decode("utf-8")
            decoded = encoding.msgpack_decode(b64_input)
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
