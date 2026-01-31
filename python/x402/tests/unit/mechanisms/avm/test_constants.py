"""Unit tests for AVM constants."""

import pytest

from x402.mechanisms.avm.constants import (
    ALGORAND_MAINNET_CAIP2,
    ALGORAND_TESTNET_CAIP2,
    BLOCKED_TXN_TYPES,
    DEFAULT_DECIMALS,
    GENESIS_HASH_TO_NETWORK,
    MAINNET_ALGOD_URL,
    MAINNET_GENESIS_HASH,
    MAX_GROUP_SIZE,
    MIN_TXN_FEE,
    NETWORK_CONFIGS,
    SCHEME_EXACT,
    SUPPORTED_NETWORKS,
    TESTNET_ALGOD_URL,
    TESTNET_GENESIS_HASH,
    TXN_TYPE_ASSET_TRANSFER,
    TXN_TYPE_KEY_REGISTRATION,
    TXN_TYPE_PAYMENT,
    USDC_MAINNET_ASA_ID,
    USDC_TESTNET_ASA_ID,
    V1_NETWORKS,
    V1_TO_V2_NETWORK_MAP,
    V2_TO_V1_NETWORK_MAP,
)


class TestSchemeConstants:
    """Tests for scheme-related constants."""

    def test_scheme_exact(self):
        """Test scheme identifier."""
        assert SCHEME_EXACT == "exact"


class TestNetworkConstants:
    """Tests for network-related constants."""

    def test_mainnet_caip2(self):
        """Test mainnet CAIP-2 identifier."""
        assert ALGORAND_MAINNET_CAIP2 == "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="
        assert ALGORAND_MAINNET_CAIP2.startswith("algorand:")

    def test_testnet_caip2(self):
        """Test testnet CAIP-2 identifier."""
        assert ALGORAND_TESTNET_CAIP2 == "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="
        assert ALGORAND_TESTNET_CAIP2.startswith("algorand:")

    def test_genesis_hashes(self):
        """Test genesis hash constants."""
        assert MAINNET_GENESIS_HASH == "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="
        assert TESTNET_GENESIS_HASH == "SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="

    def test_algod_urls(self):
        """Test Algod URL constants."""
        assert MAINNET_ALGOD_URL == "https://mainnet-api.algonode.cloud"
        assert TESTNET_ALGOD_URL == "https://testnet-api.algonode.cloud"

    def test_supported_networks(self):
        """Test supported networks list."""
        assert ALGORAND_MAINNET_CAIP2 in SUPPORTED_NETWORKS
        assert ALGORAND_TESTNET_CAIP2 in SUPPORTED_NETWORKS
        assert len(SUPPORTED_NETWORKS) == 2


class TestV1Compatibility:
    """Tests for V1 compatibility constants."""

    def test_v1_networks(self):
        """Test V1 network names."""
        assert "algorand-mainnet" in V1_NETWORKS
        assert "algorand-testnet" in V1_NETWORKS

    def test_v1_to_v2_mapping(self):
        """Test V1 to V2 network mapping."""
        assert V1_TO_V2_NETWORK_MAP["algorand-mainnet"] == ALGORAND_MAINNET_CAIP2
        assert V1_TO_V2_NETWORK_MAP["algorand-testnet"] == ALGORAND_TESTNET_CAIP2
        assert V1_TO_V2_NETWORK_MAP["algorand"] == ALGORAND_MAINNET_CAIP2

    def test_v2_to_v1_mapping(self):
        """Test V2 to V1 network mapping."""
        assert V2_TO_V1_NETWORK_MAP[ALGORAND_MAINNET_CAIP2] == "algorand-mainnet"
        assert V2_TO_V1_NETWORK_MAP[ALGORAND_TESTNET_CAIP2] == "algorand-testnet"


class TestAssetConstants:
    """Tests for asset-related constants."""

    def test_usdc_asa_ids(self):
        """Test USDC ASA IDs."""
        assert USDC_MAINNET_ASA_ID == 31566704
        assert USDC_TESTNET_ASA_ID == 10458941

    def test_default_decimals(self):
        """Test default decimals."""
        assert DEFAULT_DECIMALS == 6


class TestTransactionConstants:
    """Tests for transaction-related constants."""

    def test_min_txn_fee(self):
        """Test minimum transaction fee."""
        assert MIN_TXN_FEE == 1000

    def test_max_group_size(self):
        """Test maximum group size."""
        assert MAX_GROUP_SIZE == 16

    def test_txn_types(self):
        """Test transaction type identifiers."""
        assert TXN_TYPE_PAYMENT == "pay"
        assert TXN_TYPE_ASSET_TRANSFER == "axfer"
        assert TXN_TYPE_KEY_REGISTRATION == "keyreg"

    def test_blocked_txn_types(self):
        """Test blocked transaction types."""
        assert TXN_TYPE_KEY_REGISTRATION in BLOCKED_TXN_TYPES


class TestNetworkConfigs:
    """Tests for network configuration dictionaries."""

    def test_mainnet_config(self):
        """Test mainnet configuration."""
        config = NETWORK_CONFIGS[ALGORAND_MAINNET_CAIP2]
        assert config["algod_url"] == MAINNET_ALGOD_URL
        assert config["genesis_hash"] == MAINNET_GENESIS_HASH
        assert config["genesis_id"] == "mainnet-v1.0"
        assert config["default_asset"]["asa_id"] == USDC_MAINNET_ASA_ID
        assert config["default_asset"]["name"] == "USDC"
        assert config["default_asset"]["decimals"] == 6

    def test_testnet_config(self):
        """Test testnet configuration."""
        config = NETWORK_CONFIGS[ALGORAND_TESTNET_CAIP2]
        assert config["algod_url"] == TESTNET_ALGOD_URL
        assert config["genesis_hash"] == TESTNET_GENESIS_HASH
        assert config["genesis_id"] == "testnet-v1.0"
        assert config["default_asset"]["asa_id"] == USDC_TESTNET_ASA_ID

    def test_genesis_hash_to_network(self):
        """Test genesis hash to network mapping."""
        assert GENESIS_HASH_TO_NETWORK[MAINNET_GENESIS_HASH] == ALGORAND_MAINNET_CAIP2
        assert GENESIS_HASH_TO_NETWORK[TESTNET_GENESIS_HASH] == ALGORAND_TESTNET_CAIP2
