"""Unit tests for AVM module exports."""

import pytest


class TestModuleExports:
    """Tests for module public API exports."""

    def test_constants_exported(self):
        """Test that constants are exported."""
        from x402.mechanisms.avm import (
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

        assert SCHEME_EXACT == "exact"
        assert ALGORAND_MAINNET_CAIP2.startswith("algorand:")
        assert ALGORAND_TESTNET_CAIP2.startswith("algorand:")

    def test_types_exported(self):
        """Test that types are exported."""
        from x402.mechanisms.avm import (
            DecodedTransactionInfo,
            ExactAvmPayload,
            ExactAvmPayloadV1,
            ExactAvmPayloadV2,
            TransactionGroupInfo,
        )

        # Verify they're the same class (aliases)
        assert ExactAvmPayloadV1 is ExactAvmPayload
        assert ExactAvmPayloadV2 is ExactAvmPayload

    def test_signer_protocols_exported(self):
        """Test that signer protocols are exported."""
        from x402.mechanisms.avm import (
            ClientAvmSigner,
            FacilitatorAvmSigner,
        )

        # They should be Protocol classes
        assert hasattr(ClientAvmSigner, "__protocol_attrs__") or hasattr(
            ClientAvmSigner, "__abstractmethods__"
        )

    def test_signer_implementations_exported(self):
        """Test that signer implementations are exported."""
        from x402.mechanisms.avm import (
            AlgorandSigner,
            FacilitatorAlgorandSigner,
        )

        # They should be classes
        assert isinstance(AlgorandSigner, type)
        assert isinstance(FacilitatorAlgorandSigner, type)

    def test_utilities_exported(self):
        """Test that utilities are exported."""
        from x402.mechanisms.avm import (
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

        # Verify they're callable
        assert callable(normalize_network)
        assert callable(is_valid_address)
        assert callable(to_atomic_amount)

    def test_exact_submodule_exported(self):
        """Test that exact submodule is exported."""
        from x402.mechanisms.avm import exact

        assert hasattr(exact, "ExactAvmScheme")
        assert hasattr(exact, "ExactAvmClientScheme")
        assert hasattr(exact, "ExactAvmServerScheme")
        assert hasattr(exact, "ExactAvmFacilitatorScheme")


class TestExactModuleExports:
    """Tests for exact submodule exports."""

    def test_schemes_exported(self):
        """Test that schemes are exported."""
        from x402.mechanisms.avm.exact import (
            ExactAvmClientScheme,
            ExactAvmFacilitatorScheme,
            ExactAvmScheme,
            ExactAvmServerScheme,
        )

        # Verify they're classes
        assert isinstance(ExactAvmClientScheme, type)
        assert isinstance(ExactAvmServerScheme, type)
        assert isinstance(ExactAvmFacilitatorScheme, type)
        # ExactAvmScheme is alias for client
        assert ExactAvmScheme is ExactAvmClientScheme

    def test_registration_helpers_exported(self):
        """Test that registration helpers are exported."""
        from x402.mechanisms.avm.exact import (
            register_exact_avm_client,
            register_exact_avm_facilitator,
            register_exact_avm_server,
        )

        assert callable(register_exact_avm_client)
        assert callable(register_exact_avm_server)
        assert callable(register_exact_avm_facilitator)

    def test_v1_submodule_exported(self):
        """Test that v1 submodule is exported."""
        from x402.mechanisms.avm.exact import v1

        assert hasattr(v1, "ExactAvmSchemeV1")
        assert hasattr(v1, "ExactAvmSchemeV1Client")
        assert hasattr(v1, "ExactAvmSchemeV1Facilitator")


class TestV1ModuleExports:
    """Tests for V1 submodule exports."""

    def test_v1_schemes_exported(self):
        """Test that V1 schemes are exported."""
        from x402.mechanisms.avm.exact.v1 import (
            ExactAvmSchemeV1,
            ExactAvmSchemeV1Client,
            ExactAvmSchemeV1Facilitator,
        )

        assert isinstance(ExactAvmSchemeV1Client, type)
        assert isinstance(ExactAvmSchemeV1Facilitator, type)
        # ExactAvmSchemeV1 is alias for client
        assert ExactAvmSchemeV1 is ExactAvmSchemeV1Client
