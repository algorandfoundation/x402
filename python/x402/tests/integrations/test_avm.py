"""AVM integration tests for x402ClientSync, x402ResourceServerSync, and x402FacilitatorSync.

These tests perform REAL blockchain transactions on Algorand Testnet using sync classes.

Required environment variables:
- CLIENT_PRIVATE_KEY: Base64-encoded 64-byte key for the client (payer)
- FACILITATOR_PRIVATE_KEY: Base64-encoded 64-byte key for the facilitator (fee payer)

These must be funded accounts on Algorand Testnet with ALGO and USDC (ASA 10458941).
"""

import base64
import os

import pytest

import algosdk
import algosdk.encoding
import algosdk.transaction
import algosdk.v2client.algod
from algosdk.v2client.models import SimulateRequest, SimulateRequestTransactionGroup

from x402 import x402ClientSync, x402FacilitatorSync, x402ResourceServerSync
from x402.mechanisms.avm import (
    ALGORAND_TESTNET_CAIP2,
    SCHEME_EXACT,
    USDC_TESTNET_ASA_ID,
)
from x402.mechanisms.avm.exact import (
    ExactAvmClientScheme,
    ExactAvmFacilitatorScheme,
    ExactAvmServerScheme,
)
from x402.schemas import (
    PaymentPayload,
    PaymentRequirements,
    ResourceConfig,
    ResourceInfo,
    SettleResponse,
    SupportedResponse,
    VerifyResponse,
)

# =============================================================================
# Environment Variable Loading
# =============================================================================

CLIENT_PRIVATE_KEY = os.environ.get("CLIENT_PRIVATE_KEY")
FACILITATOR_PRIVATE_KEY = os.environ.get("FACILITATOR_PRIVATE_KEY")

# Custom Algod URL (optional, defaults to AlgoNode testnet)
ALGOD_URL = os.environ.get("ALGOD_URL", "https://testnet-api.algonode.cloud")

# USDC ASA ID on Algorand Testnet
USDC_ASA_ID = str(USDC_TESTNET_ASA_ID)

# Skip all tests if environment variables aren't set
pytestmark = pytest.mark.skipif(
    not CLIENT_PRIVATE_KEY or not FACILITATOR_PRIVATE_KEY,
    reason="CLIENT_PRIVATE_KEY and FACILITATOR_PRIVATE_KEY environment variables required for AVM integration tests",
)


# =============================================================================
# Client Signer Implementation
# =============================================================================


class AlgorandClientSigner:
    """Implements the ClientAvmSigner protocol for integration tests."""

    def __init__(self, secret_key: bytes, address: str):
        """Create signer.

        Args:
            secret_key: 64-byte secret key (32-byte seed + 32-byte public key).
            address: Algorand address.
        """
        self._secret_key = secret_key
        self._address = address

    @property
    def address(self) -> str:
        """Get signer address."""
        return self._address

    def sign_transactions(
        self,
        unsigned_txns: list[bytes],
        indexes_to_sign: list[int],
    ) -> list[bytes | None]:
        """Sign transactions at specified indexes.

        Args:
            unsigned_txns: List of unsigned transaction bytes (raw msgpack).
            indexes_to_sign: Indexes to sign.

        Returns:
            List of signed transaction bytes (or None for unsigned).
        """
        sk_b64 = base64.b64encode(self._secret_key).decode()
        result: list[bytes | None] = []
        for i, txn_bytes in enumerate(unsigned_txns):
            if i in indexes_to_sign:
                txn = algosdk.encoding.msgpack_decode(
                    base64.b64encode(txn_bytes).decode()
                )
                signed = txn.sign(sk_b64)
                result.append(
                    base64.b64decode(algosdk.encoding.msgpack_encode(signed))
                )
            else:
                result.append(None)
        return result


# =============================================================================
# Facilitator Signer Implementation
# =============================================================================


class AlgorandFacilitatorSigner:
    """Implements the FacilitatorAvmSigner protocol for integration tests."""

    def __init__(self, secret_key: bytes, address: str, algod_client):
        """Create signer.

        Args:
            secret_key: 64-byte secret key.
            address: Algorand address.
            algod_client: Algod client for network operations.
        """
        self._secret_key = secret_key
        self._address = address
        self._algod = algod_client

    def get_addresses(self) -> list[str]:
        """Get facilitator addresses."""
        return [self._address]

    def sign_transaction(self, txn_bytes: bytes, fee_payer: str, network: str) -> bytes:
        """Sign a transaction.

        Args:
            txn_bytes: Raw transaction bytes.
            fee_payer: Expected fee payer address.
            network: Network identifier.

        Returns:
            Signed transaction bytes.
        """
        if fee_payer != self._address:
            raise ValueError(f"Unknown fee payer: {fee_payer}")
        sk_b64 = base64.b64encode(self._secret_key).decode()
        txn = algosdk.encoding.msgpack_decode(base64.b64encode(txn_bytes).decode())
        signed = txn.sign(sk_b64)
        return base64.b64decode(algosdk.encoding.msgpack_encode(signed))

    def sign_group(
        self,
        group_bytes: list[bytes],
        fee_payer: str,
        indexes_to_sign: list[int],
        network: str,
    ) -> list[bytes]:
        """Sign transactions in a group at specified indexes.

        Args:
            group_bytes: List of transaction bytes.
            fee_payer: Fee payer address.
            indexes_to_sign: Indexes to sign.
            network: Network identifier.

        Returns:
            List of transaction bytes with signed ones replaced.
        """
        if fee_payer != self._address:
            raise ValueError(f"Unknown fee payer: {fee_payer}")
        sk_b64 = base64.b64encode(self._secret_key).decode()
        result = list(group_bytes)
        for i in indexes_to_sign:
            txn = algosdk.encoding.msgpack_decode(
                base64.b64encode(group_bytes[i]).decode()
            )
            signed = txn.sign(sk_b64)
            result[i] = base64.b64decode(algosdk.encoding.msgpack_encode(signed))
        return result

    def simulate_group(self, group_bytes: list[bytes], network: str) -> None:
        """Simulate a transaction group.

        Args:
            group_bytes: List of signed transaction bytes.
            network: Network identifier.

        Raises:
            Exception: If simulation fails.
        """
        decoded_txns = []
        for txn_bytes in group_bytes:
            b64 = base64.b64encode(txn_bytes).decode()
            obj = algosdk.encoding.msgpack_decode(b64)
            if isinstance(obj, algosdk.transaction.SignedTransaction):
                decoded_txns.append(obj)
            else:
                decoded_txns.append(
                    algosdk.transaction.SignedTransaction(obj, None)
                )
        request = SimulateRequest(
            txn_groups=[
                SimulateRequestTransactionGroup(txns=decoded_txns)
            ],
            allow_unnamed_resources=True,
            allow_empty_signatures=True,
        )
        result = self._algod.simulate_transactions(request)
        if result.get("txn-groups") and result["txn-groups"][0].get("failure-message"):
            raise Exception(
                f"Simulation failed: {result['txn-groups'][0]['failure-message']}"
            )

    def send_group(self, group_bytes: list[bytes], network: str) -> str:
        """Send a transaction group to the network.

        Args:
            group_bytes: List of signed transaction bytes.
            network: Network identifier.

        Returns:
            Transaction ID.
        """
        raw_group = b"".join(group_bytes)
        txid = self._algod.send_raw_transaction(base64.b64encode(raw_group))
        return txid

    def confirm_transaction(self, txid: str, network: str, rounds: int = 4) -> None:
        """Wait for transaction confirmation.

        Args:
            txid: Transaction ID.
            network: Network identifier.
            rounds: Number of rounds to wait.
        """
        algosdk.transaction.wait_for_confirmation(self._algod, txid, rounds)


# =============================================================================
# Facilitator Client Wrapper
# =============================================================================


class AvmFacilitatorClientSync:
    """Facilitator client wrapper for the x402ResourceServerSync."""

    scheme = SCHEME_EXACT
    network = ALGORAND_TESTNET_CAIP2
    x402_version = 2

    def __init__(self, facilitator: x402FacilitatorSync):
        """Create wrapper.

        Args:
            facilitator: The x402FacilitatorSync to wrap.
        """
        self._facilitator = facilitator

    def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """Verify payment."""
        return self._facilitator.verify(payload, requirements)

    def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """Settle payment."""
        return self._facilitator.settle(payload, requirements)

    def get_supported(self) -> SupportedResponse:
        """Get supported kinds."""
        return self._facilitator.get_supported()


# =============================================================================
# Helper Functions
# =============================================================================


def build_avm_payment_requirements(
    pay_to: str,
    amount: str,
    network: str = ALGORAND_TESTNET_CAIP2,
    fee_payer: str | None = None,
) -> PaymentRequirements:
    """Build AVM payment requirements for testing.

    Args:
        pay_to: Recipient address (Algorand).
        amount: Amount in smallest units (e.g., "1000" for 0.001 USDC).
        network: Network identifier.
        fee_payer: Optional fee payer address.

    Returns:
        Payment requirements.
    """
    extra = {}
    if fee_payer:
        extra["feePayer"] = fee_payer

    return PaymentRequirements(
        scheme=SCHEME_EXACT,
        network=network,
        asset=USDC_ASA_ID,
        amount=amount,
        pay_to=pay_to,
        max_timeout_seconds=3600,
        extra=extra,
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestAvmIntegrationV2:
    """Integration tests for AVM V2 payment flow with REAL blockchain transactions."""

    def setup_method(self) -> None:
        """Set up test fixtures with real blockchain clients."""
        # Decode private keys
        client_secret_key = base64.b64decode(CLIENT_PRIVATE_KEY)
        facilitator_secret_key = base64.b64decode(FACILITATOR_PRIVATE_KEY)

        assert len(client_secret_key) == 64, "Client key must be 64 bytes"
        assert len(facilitator_secret_key) == 64, "Facilitator key must be 64 bytes"

        # Derive addresses
        client_address = algosdk.encoding.encode_address(client_secret_key[32:])
        facilitator_address = algosdk.encoding.encode_address(
            facilitator_secret_key[32:]
        )

        # Create Algod client
        algod_client = algosdk.v2client.algod.AlgodClient("", ALGOD_URL)

        # Create signers
        self.client_signer = AlgorandClientSigner(client_secret_key, client_address)
        self.facilitator_signer = AlgorandFacilitatorSigner(
            facilitator_secret_key, facilitator_address, algod_client
        )

        # Store addresses for assertions
        self.client_address = client_address
        self.facilitator_address = facilitator_address

        # Create client with AVM scheme
        self.client = x402ClientSync().register(
            ALGORAND_TESTNET_CAIP2,
            ExactAvmClientScheme(self.client_signer),
        )

        # Create facilitator with AVM scheme
        self.facilitator = x402FacilitatorSync().register(
            [ALGORAND_TESTNET_CAIP2],
            ExactAvmFacilitatorScheme(self.facilitator_signer),
        )

        # Create facilitator client wrapper
        facilitator_client = AvmFacilitatorClientSync(self.facilitator)

        # Create resource server with AVM scheme
        self.server = x402ResourceServerSync(facilitator_client)
        self.server.register(ALGORAND_TESTNET_CAIP2, ExactAvmServerScheme())
        self.server.initialize()

    def test_server_should_successfully_verify_and_settle_avm_payment_from_client(
        self,
    ) -> None:
        """Test the complete AVM V2 payment flow with REAL blockchain transactions.

        This test:
        1. Creates payment requirements
        2. Client signs an ASA transfer transaction
        3. Server verifies the transaction structure
        4. Server settles by submitting the transaction to Algorand Testnet

        WARNING: This will spend real testnet USDC!
        """
        # Use facilitator address as recipient for testing
        recipient = self.facilitator_address

        # Server - builds PaymentRequired response
        accepts = [
            build_avm_payment_requirements(
                recipient,
                "1000",  # 0.001 USDC (1000 units with 6 decimals)
                fee_payer=self.facilitator_address,
            )
        ]
        resource = ResourceInfo(
            url="https://api.example.com/premium",
            description="Premium API Access",
            mime_type="application/json",
        )
        payment_required = self.server.create_payment_required_response(
            accepts, resource
        )

        # Verify V2
        assert payment_required.x402_version == 2

        # Client - creates payment payload (signs ASA transfer transaction)
        payment_payload = self.client.create_payment_payload(payment_required)

        # Verify payload structure
        assert payment_payload.x402_version == 2
        assert payment_payload.accepted.scheme == SCHEME_EXACT
        assert payment_payload.accepted.network == ALGORAND_TESTNET_CAIP2
        assert "payment_group" in payment_payload.payload or "paymentGroup" in payment_payload.payload

        # Server - finds matching requirements
        accepted = self.server.find_matching_requirements(accepts, payment_payload)
        assert accepted is not None

        # Server - verifies payment (real transaction verification)
        verify_response = self.server.verify_payment(payment_payload, accepted)

        if not verify_response.is_valid:
            print(f"❌ Verification failed: {verify_response.invalid_reason}")
            print(f"Payer: {verify_response.payer}")
            print(f"Client address: {self.client_address}")

        assert verify_response.is_valid is True
        assert verify_response.payer == self.client_address

        # Server does work here...

        # Server - settles payment (REAL on-chain transaction!)
        settle_response = self.server.settle_payment(payment_payload, accepted)

        if not settle_response.success:
            print(f"❌ Settlement failed: {settle_response.error_reason}")

        assert settle_response.success is True
        assert settle_response.network == ALGORAND_TESTNET_CAIP2
        assert settle_response.transaction != ""
        assert settle_response.payer == self.client_address

        print(f"✅ Transaction settled: {settle_response.transaction}")

    def test_client_creates_valid_avm_payment_payload(self) -> None:
        """Test that client creates properly structured AVM payload."""
        accepts = [
            build_avm_payment_requirements(
                self.facilitator_address,
                "5000000",  # 5 USDC
                fee_payer=self.facilitator_address,
            )
        ]
        payment_required = self.server.create_payment_required_response(accepts)

        payload = self.client.create_payment_payload(payment_required)

        assert payload.x402_version == 2
        assert payload.accepted.scheme == SCHEME_EXACT
        assert payload.accepted.amount == "5000000"
        assert payload.accepted.network == ALGORAND_TESTNET_CAIP2

        # Check AVM payload structure
        p = payload.payload
        payment_group = p.get("payment_group") or p.get("paymentGroup")
        assert payment_group is not None
        assert len(payment_group) > 0
        # Transactions should be base64 encoded
        assert isinstance(payment_group[0], str)
        assert len(payment_group[0]) > 0

    def test_invalid_recipient_fails_verification(self) -> None:
        """Test that mismatched recipient fails verification."""
        # Use a valid but different Algorand address
        recipient1 = self.facilitator_address

        accepts = [
            build_avm_payment_requirements(
                recipient1,
                "1000",
                fee_payer=self.facilitator_address,
            )
        ]
        payment_required = self.server.create_payment_required_response(accepts)
        payload = self.client.create_payment_payload(payment_required)

        # Change recipient in requirements to client address (different)
        different_accepts = [
            build_avm_payment_requirements(
                self.client_address,
                "1000",
                fee_payer=self.facilitator_address,
            )
        ]

        # Manually verify with different requirements
        verify_response = self.server.verify_payment(payload, different_accepts[0])
        assert verify_response.is_valid is False
        assert "recipient" in verify_response.invalid_reason.lower()

    def test_insufficient_amount_fails_verification(self) -> None:
        """Test that insufficient amount fails verification."""
        recipient = self.facilitator_address

        accepts = [
            build_avm_payment_requirements(
                recipient,
                "1000",  # Client pays 1000
                fee_payer=self.facilitator_address,
            )
        ]
        payment_required = self.server.create_payment_required_response(accepts)
        payload = self.client.create_payment_payload(payment_required)

        # Try to verify against higher amount
        higher_accepts = [
            build_avm_payment_requirements(
                recipient,
                "2000",  # Require 2000
                fee_payer=self.facilitator_address,
            )
        ]

        verify_response = self.server.verify_payment(payload, higher_accepts[0])
        assert verify_response.is_valid is False
        assert "amount" in verify_response.invalid_reason.lower()

    def test_facilitator_get_supported(self) -> None:
        """Test that facilitator returns supported kinds."""
        supported = self.facilitator.get_supported()

        assert len(supported.kinds) >= 1

        # Find Algorand Testnet support
        avm_support = None
        for kind in supported.kinds:
            if kind.network == ALGORAND_TESTNET_CAIP2 and kind.scheme == SCHEME_EXACT:
                avm_support = kind
                break

        assert avm_support is not None
        assert avm_support.x402_version == 2

        # AVM should have feePayer in extra
        assert avm_support.extra is not None
        assert "feePayer" in avm_support.extra

    def test_fee_payer_not_managed_fails_verification(self) -> None:
        """Test that using an unmanaged fee payer fails verification."""
        recipient = self.facilitator_address
        # Use a valid but unmanaged Algorand address (all A's is valid base32)
        unknown_fee_payer = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

        # Create payment requirements with known (managed) fee payer first
        valid_accepts = [
            build_avm_payment_requirements(
                recipient,
                "1000",
                fee_payer=self.facilitator_address,
            )
        ]
        payment_required = self.server.create_payment_required_response(valid_accepts)
        payload = self.client.create_payment_payload(payment_required)

        # Now try to verify with unknown fee payer
        bad_requirements = build_avm_payment_requirements(
            recipient,
            "1000",
            fee_payer=unknown_fee_payer,
        )
        verify_response = self.server.verify_payment(payload, bad_requirements)
        assert verify_response.is_valid is False
        assert "fee_payer" in verify_response.invalid_reason.lower()


class TestAvmPriceParsing:
    """Tests for AVM server price parsing (no blockchain transactions needed)."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        facilitator_secret_key = base64.b64decode(FACILITATOR_PRIVATE_KEY)
        facilitator_address = algosdk.encoding.encode_address(
            facilitator_secret_key[32:]
        )
        algod_client = algosdk.v2client.algod.AlgodClient("", ALGOD_URL)

        self.facilitator_signer = AlgorandFacilitatorSigner(
            facilitator_secret_key, facilitator_address, algod_client
        )
        self.facilitator_address = facilitator_address

        self.facilitator = x402FacilitatorSync().register(
            [ALGORAND_TESTNET_CAIP2],
            ExactAvmFacilitatorScheme(self.facilitator_signer),
        )

        facilitator_client = AvmFacilitatorClientSync(self.facilitator)
        self.server = x402ResourceServerSync(facilitator_client)
        self.avm_server = ExactAvmServerScheme()
        self.server.register(ALGORAND_TESTNET_CAIP2, self.avm_server)
        self.server.initialize()

    def test_parse_money_formats(self) -> None:
        """Test parsing different Money formats."""
        test_cases = [
            ("$1.00", "1000000"),
            ("1.50", "1500000"),
            (2.5, "2500000"),
            ("$0.001", "1000"),
        ]

        for input_price, expected_amount in test_cases:
            config = ResourceConfig(
                scheme=SCHEME_EXACT,
                pay_to=self.facilitator_address,
                price=input_price,
                network=ALGORAND_TESTNET_CAIP2,
            )
            requirements = self.server.build_payment_requirements(config)

            assert len(requirements) == 1
            assert requirements[0].amount == expected_amount
            assert requirements[0].asset == USDC_ASA_ID

    def test_asset_amount_passthrough(self) -> None:
        """Test that AssetAmount is passed through directly."""
        from x402.schemas import AssetAmount

        custom_asset = AssetAmount(
            amount="5000000",
            asset="12345678",
            extra={"foo": "bar"},
        )

        config = ResourceConfig(
            scheme=SCHEME_EXACT,
            pay_to=self.facilitator_address,
            price=custom_asset,
            network=ALGORAND_TESTNET_CAIP2,
        )
        requirements = self.server.build_payment_requirements(config)

        assert len(requirements) == 1
        assert requirements[0].amount == "5000000"
        assert requirements[0].asset == "12345678"

    def test_custom_money_parser(self) -> None:
        """Test registering custom money parser."""
        from x402.schemas import AssetAmount

        # Register custom parser for large amounts
        def large_amount_parser(amount: float, network: str):
            if amount > 100:
                return AssetAmount(
                    amount=str(int(amount * 1_000_000)),  # 6 decimals
                    asset="99999999",
                    extra={"token": "CUSTOM", "tier": "large"},
                )
            return None

        self.avm_server.register_money_parser(large_amount_parser)

        # Large amount - should use custom parser
        config = ResourceConfig(
            scheme=SCHEME_EXACT,
            pay_to=self.facilitator_address,
            price=150,
            network=ALGORAND_TESTNET_CAIP2,
        )
        large_req = self.server.build_payment_requirements(config)

        assert large_req[0].extra.get("token") == "CUSTOM"
        assert large_req[0].extra.get("tier") == "large"

        # Small amount - should use default USDC
        config2 = ResourceConfig(
            scheme=SCHEME_EXACT,
            pay_to=self.facilitator_address,
            price=50,
            network=ALGORAND_TESTNET_CAIP2,
        )
        small_req = self.server.build_payment_requirements(config2)

        assert small_req[0].asset == USDC_ASA_ID


class TestAvmNetworkNormalization:
    """Tests for AVM network identifier normalization."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        facilitator_secret_key = base64.b64decode(FACILITATOR_PRIVATE_KEY)
        facilitator_address = algosdk.encoding.encode_address(
            facilitator_secret_key[32:]
        )
        algod_client = algosdk.v2client.algod.AlgodClient("", ALGOD_URL)

        self.facilitator_signer = AlgorandFacilitatorSigner(
            facilitator_secret_key, facilitator_address, algod_client
        )
        self.facilitator_address = facilitator_address

        # Register for testnet with CAIP-2 identifier
        self.facilitator = x402FacilitatorSync().register(
            [ALGORAND_TESTNET_CAIP2],
            ExactAvmFacilitatorScheme(self.facilitator_signer),
        )

    def test_facilitator_supports_caip2_network(self) -> None:
        """Test that facilitator correctly supports CAIP-2 network identifier."""
        supported = self.facilitator.get_supported()

        # Find testnet support
        testnet_support = None
        for kind in supported.kinds:
            if kind.network == ALGORAND_TESTNET_CAIP2:
                testnet_support = kind
                break

        assert testnet_support is not None
        assert testnet_support.scheme == SCHEME_EXACT

    def test_facilitator_extra_contains_fee_payer(self) -> None:
        """Test that facilitator's extra data contains feePayer for AVM."""
        supported = self.facilitator.get_supported()

        for kind in supported.kinds:
            if kind.network == ALGORAND_TESTNET_CAIP2:
                assert kind.extra is not None
                assert "feePayer" in kind.extra
                assert kind.extra["feePayer"] in self.facilitator_signer.get_addresses()


class TestAvmSignersIntegration:
    """Integration tests for AlgorandClientSigner and AlgorandFacilitatorSigner methods.

    These tests verify the signer interface methods work correctly.
    The full payment flow is already tested in TestAvmIntegrationV2.
    """

    def setup_method(self) -> None:
        """Set up test fixtures."""
        client_secret_key = base64.b64decode(CLIENT_PRIVATE_KEY)
        facilitator_secret_key = base64.b64decode(FACILITATOR_PRIVATE_KEY)

        self.client_address = algosdk.encoding.encode_address(client_secret_key[32:])
        self.facilitator_address = algosdk.encoding.encode_address(
            facilitator_secret_key[32:]
        )

        algod_client = algosdk.v2client.algod.AlgodClient("", ALGOD_URL)

        self.client_signer = AlgorandClientSigner(
            client_secret_key, self.client_address
        )
        self.facilitator_signer = AlgorandFacilitatorSigner(
            facilitator_secret_key, self.facilitator_address, algod_client
        )

    def test_client_signer_address(self) -> None:
        """Test that client signer returns correct address."""
        assert self.client_signer.address == self.client_address
        assert len(self.client_signer.address) == 58

    def test_facilitator_signer_address(self) -> None:
        """Test that facilitator signer returns correct address."""
        addresses = self.facilitator_signer.get_addresses()
        assert len(addresses) == 1
        assert addresses[0] == self.facilitator_address
        assert len(self.facilitator_address) == 58

    def test_facilitator_signer_get_addresses(self) -> None:
        """Test that facilitator signer returns correct addresses list."""
        addresses = self.facilitator_signer.get_addresses()

        assert len(addresses) == 1
        assert addresses[0] == self.facilitator_address

    def test_client_signer_sign_returns_correct_structure(self) -> None:
        """Test that client signer sign_transactions returns correct structure."""
        # Create a dummy transaction
        algod_client = algosdk.v2client.algod.AlgodClient("", ALGOD_URL)
        sp = algod_client.suggested_params()

        txn = algosdk.transaction.PaymentTxn(
            sender=self.client_address,
            sp=sp,
            receiver=self.client_address,
            amt=0,
            note=b"test",
        )

        # Encode transaction
        b64_encoded = algosdk.encoding.msgpack_encode(txn)
        txn_bytes = base64.b64decode(b64_encoded)

        # Sign with index 0
        results = self.client_signer.sign_transactions([txn_bytes], [0])

        assert len(results) == 1
        assert results[0] is not None
        assert isinstance(results[0], bytes)
        assert len(results[0]) > 0

    def test_client_signer_skips_unsigned_indexes(self) -> None:
        """Test that client signer returns None for non-signed indexes."""
        algod_client = algosdk.v2client.algod.AlgodClient("", ALGOD_URL)
        sp = algod_client.suggested_params()

        txn = algosdk.transaction.PaymentTxn(
            sender=self.client_address,
            sp=sp,
            receiver=self.client_address,
            amt=0,
        )

        b64_encoded = algosdk.encoding.msgpack_encode(txn)
        txn_bytes = base64.b64decode(b64_encoded)

        # Don't sign index 0
        results = self.client_signer.sign_transactions([txn_bytes], [])

        assert len(results) == 1
        assert results[0] is None
