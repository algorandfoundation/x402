"""AVM server implementation for the Exact payment scheme (V2).

Parses prices and enhances payment requirements with AVM-specific data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ....schemas import AssetAmount, Network, PaymentRequirements, Price, SupportedKind
from ..constants import DEFAULT_DECIMALS, SCHEME_EXACT
from ..utils import (
    get_network_config,
    get_usdc_asa_id,
    normalize_network,
    parse_money_to_decimal,
    to_atomic_amount,
)


# Type alias for money parser
MoneyParser = Callable[[float, str], AssetAmount | None]


class ExactAvmScheme:
    """AVM server implementation for the Exact payment scheme (V2).

    Parses prices and enhances payment requirements with AVM-specific data.

    Note: feePayer is OPTIONAL for AVM (unlike SVM which requires it).
    If not provided, the client pays their own fees.

    Attributes:
        scheme: The scheme identifier ("exact").
    """

    scheme = SCHEME_EXACT

    def __init__(self):
        """Create ExactAvmScheme."""
        self._money_parsers: list[MoneyParser] = []

    def register_money_parser(self, parser: MoneyParser) -> "ExactAvmScheme":
        """Register custom money parser in the parser chain.

        Multiple parsers can be registered - tried in registration order.
        If parser returns None, next parser is tried.

        Args:
            parser: Custom function to convert amount to AssetAmount.

        Returns:
            Self for chaining.
        """
        self._money_parsers.append(parser)
        return self

    def parse_price(self, price: Price, network: Network) -> AssetAmount:
        """Parse price into asset amount.

        If price is already AssetAmount, returns it directly.
        If price is Money (str|float), parses and tries custom parsers.
        Falls back to default USDC conversion.

        Args:
            price: Price to parse (string, number, or AssetAmount dict).
            network: Network identifier.

        Returns:
            AssetAmount with amount, asset, and extra fields.
        """
        network_str = str(network)

        # Already an AssetAmount (dict with 'amount' key)
        if isinstance(price, dict) and "amount" in price:
            return AssetAmount(
                amount=price["amount"],
                asset=price.get("asset", str(get_usdc_asa_id(network_str))),
                extra=price.get("extra", {"decimals": DEFAULT_DECIMALS}),
            )

        # Already an AssetAmount object
        if isinstance(price, AssetAmount):
            if not price.asset:
                price.asset = str(get_usdc_asa_id(network_str))
            return price

        # Parse Money to decimal
        decimal_amount = parse_money_to_decimal(price)

        # Try custom parsers
        for parser in self._money_parsers:
            result = parser(decimal_amount, network_str)
            if result is not None:
                return result

        # Default: convert to USDC
        return self._default_money_conversion(decimal_amount, network_str)

    def _default_money_conversion(self, amount: float, network: str) -> AssetAmount:
        """Convert decimal USD amount to USDC AssetAmount.

        Args:
            amount: Decimal USD amount.
            network: Network identifier.

        Returns:
            AssetAmount in USDC.
        """
        asa_id = get_usdc_asa_id(network)
        atomic_amount = to_atomic_amount(amount, DEFAULT_DECIMALS)

        return AssetAmount(
            amount=str(atomic_amount),
            asset=str(asa_id),
            extra={"decimals": DEFAULT_DECIMALS},
        )

    def enhance_payment_requirements(
        self,
        requirements: PaymentRequirements,
        supported_kind: SupportedKind,
        extension_keys: list[str],
    ) -> PaymentRequirements:
        """Add scheme-specific enhancements to payment requirements.

        For AVM:
        - Adds decimals to extra (required for display)
        - Adds feePayer from facilitator if provided (OPTIONAL)
        - Adds genesis info if available

        Args:
            requirements: Base payment requirements.
            supported_kind: Supported kind from facilitator.
            extension_keys: Extension keys being used.

        Returns:
            Enhanced payment requirements.
        """
        _ = extension_keys  # Unused

        if requirements.extra is None:
            requirements.extra = {}

        # Add decimals for client display calculations
        if "decimals" not in requirements.extra:
            requirements.extra["decimals"] = DEFAULT_DECIMALS

        # Add feePayer from facilitator's supported kind extra
        # This is OPTIONAL for AVM - if not provided, client pays fees
        facilitator_extra = supported_kind.extra
        if facilitator_extra and "feePayer" in facilitator_extra:
            requirements.extra["feePayer"] = facilitator_extra["feePayer"]

        # Add genesis info if not present (helps clients validate network)
        try:
            network_str = str(requirements.network)
            config = get_network_config(network_str)
            if "genesisHash" not in requirements.extra:
                requirements.extra["genesisHash"] = config["genesis_hash"]
            if "genesisId" not in requirements.extra:
                requirements.extra["genesisId"] = config["genesis_id"]
        except ValueError:
            pass  # Network not found, skip genesis info

        return requirements

    def get_asset_info(self, network: str, asset: str) -> dict[str, Any]:
        """Get information about an asset.

        Args:
            network: Network identifier.
            asset: ASA ID as string.

        Returns:
            Asset info with name, decimals, asa_id.
        """
        caip2_network = normalize_network(network)

        # For now, only USDC is supported
        asa_id = int(asset)
        config = get_network_config(caip2_network)

        if asa_id == config["default_asset"]["asa_id"]:
            return {
                "asa_id": asa_id,
                "name": config["default_asset"]["name"],
                "decimals": config["default_asset"]["decimals"],
            }

        # Unknown asset - return with default decimals
        return {
            "asa_id": asa_id,
            "name": f"ASA-{asa_id}",
            "decimals": DEFAULT_DECIMALS,
        }
