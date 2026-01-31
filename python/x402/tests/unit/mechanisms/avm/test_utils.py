"""Unit tests for AVM utilities."""

import pytest

from x402.mechanisms.avm.constants import (
    ALGORAND_MAINNET_CAIP2,
    ALGORAND_TESTNET_CAIP2,
    DEFAULT_DECIMALS,
    MAINNET_GENESIS_HASH,
    TESTNET_GENESIS_HASH,
    USDC_MAINNET_ASA_ID,
    USDC_TESTNET_ASA_ID,
)
from x402.mechanisms.avm.utils import (
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
)


class TestAddressValidation:
    """Tests for address validation."""

    def test_valid_address(self):
        """Test valid Algorand address."""
        # Zero address (58 A's)
        assert is_valid_address("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ")

    def test_invalid_address_wrong_length(self):
        """Test invalid address with wrong length."""
        assert not is_valid_address("AAAA")
        assert not is_valid_address("A" * 57)
        assert not is_valid_address("A" * 59)

    def test_invalid_address_wrong_chars(self):
        """Test invalid address with invalid characters."""
        # Lowercase
        assert not is_valid_address("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaay5hfkq")
        # Invalid chars (0, 1, 8, 9)
        assert not is_valid_address("01890000000000000000000000000000000000000000000000000000AB")

    def test_invalid_address_empty(self):
        """Test invalid address - empty or None."""
        assert not is_valid_address("")
        assert not is_valid_address(None)  # type: ignore


class TestNetworkNormalization:
    """Tests for network normalization."""

    def test_normalize_mainnet_caip2(self):
        """Test normalizing mainnet CAIP-2."""
        assert normalize_network(ALGORAND_MAINNET_CAIP2) == ALGORAND_MAINNET_CAIP2

    def test_normalize_testnet_caip2(self):
        """Test normalizing testnet CAIP-2."""
        assert normalize_network(ALGORAND_TESTNET_CAIP2) == ALGORAND_TESTNET_CAIP2

    def test_normalize_v1_mainnet(self):
        """Test normalizing V1 mainnet name."""
        assert normalize_network("algorand-mainnet") == ALGORAND_MAINNET_CAIP2

    def test_normalize_v1_testnet(self):
        """Test normalizing V1 testnet name."""
        assert normalize_network("algorand-testnet") == ALGORAND_TESTNET_CAIP2

    def test_normalize_algorand_shorthand(self):
        """Test normalizing 'algorand' shorthand."""
        assert normalize_network("algorand") == ALGORAND_MAINNET_CAIP2

    def test_normalize_unsupported(self):
        """Test normalizing unsupported network."""
        with pytest.raises(ValueError):
            normalize_network("ethereum")

    def test_normalize_invalid_caip2(self):
        """Test normalizing invalid CAIP-2."""
        with pytest.raises(ValueError):
            normalize_network("algorand:invalid-hash")


class TestNetworkValidation:
    """Tests for network validation."""

    def test_valid_networks(self):
        """Test valid networks."""
        assert is_valid_network(ALGORAND_MAINNET_CAIP2)
        assert is_valid_network(ALGORAND_TESTNET_CAIP2)
        assert is_valid_network("algorand-mainnet")
        assert is_valid_network("algorand-testnet")
        assert is_valid_network("algorand")

    def test_invalid_networks(self):
        """Test invalid networks."""
        assert not is_valid_network("ethereum")
        assert not is_valid_network("solana")
        assert not is_valid_network("algorand:invalid")


class TestNetworkConfig:
    """Tests for network configuration retrieval."""

    def test_get_mainnet_config(self):
        """Test getting mainnet config."""
        config = get_network_config(ALGORAND_MAINNET_CAIP2)
        assert "algod_url" in config
        assert "genesis_hash" in config
        assert config["genesis_hash"] == MAINNET_GENESIS_HASH

    def test_get_testnet_config(self):
        """Test getting testnet config."""
        config = get_network_config(ALGORAND_TESTNET_CAIP2)
        assert config["genesis_hash"] == TESTNET_GENESIS_HASH

    def test_get_config_v1_name(self):
        """Test getting config with V1 name."""
        config = get_network_config("algorand-mainnet")
        assert config["genesis_hash"] == MAINNET_GENESIS_HASH

    def test_get_config_invalid(self):
        """Test getting config for invalid network."""
        with pytest.raises(ValueError):
            get_network_config("invalid")


class TestUsdcAsaId:
    """Tests for USDC ASA ID retrieval."""

    def test_mainnet_usdc(self):
        """Test mainnet USDC ASA ID."""
        assert get_usdc_asa_id(ALGORAND_MAINNET_CAIP2) == USDC_MAINNET_ASA_ID

    def test_testnet_usdc(self):
        """Test testnet USDC ASA ID."""
        assert get_usdc_asa_id(ALGORAND_TESTNET_CAIP2) == USDC_TESTNET_ASA_ID

    def test_usdc_v1_name(self):
        """Test USDC with V1 name."""
        assert get_usdc_asa_id("algorand-mainnet") == USDC_MAINNET_ASA_ID


class TestGenesisHash:
    """Tests for genesis hash operations."""

    def test_get_genesis_hash_mainnet(self):
        """Test getting mainnet genesis hash."""
        assert get_genesis_hash(ALGORAND_MAINNET_CAIP2) == MAINNET_GENESIS_HASH

    def test_get_genesis_hash_testnet(self):
        """Test getting testnet genesis hash."""
        assert get_genesis_hash(ALGORAND_TESTNET_CAIP2) == TESTNET_GENESIS_HASH

    def test_network_from_genesis_hash_mainnet(self):
        """Test network from mainnet genesis hash."""
        assert network_from_genesis_hash(MAINNET_GENESIS_HASH) == ALGORAND_MAINNET_CAIP2

    def test_network_from_genesis_hash_testnet(self):
        """Test network from testnet genesis hash."""
        assert network_from_genesis_hash(TESTNET_GENESIS_HASH) == ALGORAND_TESTNET_CAIP2

    def test_network_from_genesis_hash_unknown(self):
        """Test network from unknown genesis hash."""
        assert network_from_genesis_hash("unknown") is None


class TestMoneyParsing:
    """Tests for money parsing utilities."""

    def test_parse_string_amount(self):
        """Test parsing string amount."""
        assert parse_money_to_decimal("100") == 100.0
        assert parse_money_to_decimal("100.50") == 100.5

    def test_parse_string_with_dollar(self):
        """Test parsing string with dollar sign."""
        assert parse_money_to_decimal("$100") == 100.0
        assert parse_money_to_decimal("$100.50") == 100.5

    def test_parse_string_with_commas(self):
        """Test parsing string with comma separators."""
        assert parse_money_to_decimal("1,000") == 1000.0
        assert parse_money_to_decimal("$1,000.50") == 1000.5

    def test_parse_float(self):
        """Test parsing float amount."""
        assert parse_money_to_decimal(100.0) == 100.0
        assert parse_money_to_decimal(100.5) == 100.5

    def test_parse_int(self):
        """Test parsing integer amount."""
        assert parse_money_to_decimal(100) == 100.0


class TestAtomicConversion:
    """Tests for atomic unit conversion."""

    def test_to_atomic_default_decimals(self):
        """Test conversion to atomic units with default decimals."""
        assert to_atomic_amount(1.0) == 1000000
        assert to_atomic_amount(0.5) == 500000
        assert to_atomic_amount(0.000001) == 1

    def test_to_atomic_custom_decimals(self):
        """Test conversion to atomic units with custom decimals."""
        assert to_atomic_amount(1.0, 2) == 100
        assert to_atomic_amount(1.0, 8) == 100000000

    def test_from_atomic_default_decimals(self):
        """Test conversion from atomic units with default decimals."""
        assert from_atomic_amount(1000000) == 1.0
        assert from_atomic_amount(500000) == 0.5
        assert from_atomic_amount(1) == 0.000001

    def test_from_atomic_custom_decimals(self):
        """Test conversion from atomic units with custom decimals."""
        assert from_atomic_amount(100, 2) == 1.0
        assert from_atomic_amount(100000000, 8) == 1.0

    def test_roundtrip(self):
        """Test roundtrip conversion."""
        original = 123.456789
        atomic = to_atomic_amount(original)
        restored = from_atomic_amount(atomic)
        assert abs(restored - original) < 0.000001
