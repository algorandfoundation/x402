"""Unit tests for AVM types."""

import pytest

from x402.mechanisms.avm.types import (
    DecodedTransactionInfo,
    ExactAvmPayload,
    TransactionGroupInfo,
)


class TestExactAvmPayload:
    """Tests for ExactAvmPayload dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        payload = ExactAvmPayload()
        assert payload.payment_group == []
        assert payload.payment_index == 0

    def test_custom_values(self):
        """Test initialization with custom values."""
        payload = ExactAvmPayload(
            payment_group=["dHhuMQ==", "dHhuMg=="],
            payment_index=1,
        )
        assert payload.payment_group == ["dHhuMQ==", "dHhuMg=="]
        assert payload.payment_index == 1

    def test_to_dict(self):
        """Test conversion to dictionary."""
        payload = ExactAvmPayload(
            payment_group=["dHhuMQ==", "dHhuMg=="],
            payment_index=1,
        )
        result = payload.to_dict()
        assert result == {
            "paymentGroup": ["dHhuMQ==", "dHhuMg=="],
            "paymentIndex": 1,
        }

    def test_to_dict_camel_case(self):
        """Test that to_dict uses camelCase keys."""
        payload = ExactAvmPayload(payment_group=["abc"], payment_index=0)
        result = payload.to_dict()
        assert "paymentGroup" in result
        assert "paymentIndex" in result
        assert "payment_group" not in result
        assert "payment_index" not in result

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "paymentGroup": ["dHhuMQ==", "dHhuMg=="],
            "paymentIndex": 1,
        }
        payload = ExactAvmPayload.from_dict(data)
        assert payload.payment_group == ["dHhuMQ==", "dHhuMg=="]
        assert payload.payment_index == 1

    def test_from_dict_missing_keys(self):
        """Test from_dict with missing keys uses defaults."""
        data = {}
        payload = ExactAvmPayload.from_dict(data)
        assert payload.payment_group == []
        assert payload.payment_index == 0

    def test_roundtrip(self):
        """Test to_dict and from_dict roundtrip."""
        original = ExactAvmPayload(
            payment_group=["abc", "def"],
            payment_index=1,
        )
        data = original.to_dict()
        restored = ExactAvmPayload.from_dict(data)
        assert restored.payment_group == original.payment_group
        assert restored.payment_index == original.payment_index


class TestDecodedTransactionInfo:
    """Tests for DecodedTransactionInfo dataclass."""

    def test_minimal_initialization(self):
        """Test initialization with required fields only."""
        info = DecodedTransactionInfo(
            type="pay",
            sender="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ",
            fee=1000,
            first_valid=1000,
            last_valid=2000,
            genesis_hash="wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
        )
        assert info.type == "pay"
        assert info.sender == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
        assert info.fee == 1000
        assert info.is_signed is False
        assert info.rekey_to is None

    def test_full_initialization(self):
        """Test initialization with all fields."""
        info = DecodedTransactionInfo(
            type="axfer",
            sender="SENDER",
            fee=1000,
            first_valid=1000,
            last_valid=2000,
            genesis_hash="wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
            genesis_id="mainnet-v1.0",
            group="abc123",
            is_signed=True,
            note=b"test note",
            asset_index=31566704,
            asset_receiver="RECEIVER",
            asset_amount=1000000,
        )
        assert info.type == "axfer"
        assert info.is_signed is True
        assert info.asset_index == 31566704
        assert info.asset_amount == 1000000

    def test_payment_fields(self):
        """Test payment-specific fields."""
        info = DecodedTransactionInfo(
            type="pay",
            sender="SENDER",
            fee=1000,
            first_valid=1000,
            last_valid=2000,
            genesis_hash="hash",
            receiver="RECEIVER",
            amount=1000000,
            close_remainder_to="CLOSE",
        )
        assert info.receiver == "RECEIVER"
        assert info.amount == 1000000
        assert info.close_remainder_to == "CLOSE"


class TestTransactionGroupInfo:
    """Tests for TransactionGroupInfo dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        info = TransactionGroupInfo(transactions=[])
        assert info.transactions == []
        assert info.group_id is None
        assert info.total_fee == 0
        assert info.has_fee_payer is False
        assert info.fee_payer_index is None
        assert info.payment_index == 0

    def test_with_transactions(self):
        """Test with transaction list."""
        txn1 = DecodedTransactionInfo(
            type="pay", sender="A", fee=2000,
            first_valid=1000, last_valid=2000, genesis_hash="hash"
        )
        txn2 = DecodedTransactionInfo(
            type="axfer", sender="B", fee=0,
            first_valid=1000, last_valid=2000, genesis_hash="hash"
        )
        info = TransactionGroupInfo(
            transactions=[txn1, txn2],
            group_id="group123",
            total_fee=2000,
            has_fee_payer=True,
            fee_payer_index=0,
            payment_index=1,
        )
        assert len(info.transactions) == 2
        assert info.group_id == "group123"
        assert info.total_fee == 2000
        assert info.has_fee_payer is True
        assert info.fee_payer_index == 0
        assert info.payment_index == 1
