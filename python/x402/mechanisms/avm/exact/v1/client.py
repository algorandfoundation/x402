"""V1 client implementation for AVM exact payment scheme.

Provides backward compatibility for V1 protocol by wrapping the V2 implementation.
Maps V1 network names (algorand-mainnet, algorand-testnet) to V2 CAIP-2 identifiers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...constants import V1_TO_V2_NETWORK_MAP

if TYPE_CHECKING:
    from ...signer import ClientAvmSigner


class ExactAvmSchemeV1:
    """V1 client implementation for AVM exact payment scheme.

    Wraps V2 ExactAvmScheme with V1 network name support and
    field name mapping (maxAmountRequired -> amount).

    This implements SchemeNetworkClientV1 protocol.

    Attributes:
        scheme: The scheme identifier ("exact").
    """

    scheme = "exact"

    def __init__(self, signer: "ClientAvmSigner", algod_url: str | None = None):
        """Create ExactAvmSchemeV1.

        Args:
            signer: AVM signer for payment authorizations.
            algod_url: Optional custom Algod URL.
        """
        # Import here to avoid circular imports
        from ..client import ExactAvmScheme

        self._v2_scheme = ExactAvmScheme(signer, algod_url)

    def create_payment_payload(
        self,
        payment_requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Create payment payload for V1 protocol.

        Converts V1 payment requirements to V2 format, creates payload,
        and returns V1-compatible response.

        Args:
            payment_requirements: V1 payment requirements dict with:
                - scheme: str
                - network: str (V1 network name)
                - maxAmountRequired: str
                - resource: str
                - payTo: str
                - asset: str
                - extra: dict | None

        Returns:
            V1 payment payload dict.
        """
        # Import PaymentRequirements for conversion
        from .....schemas import PaymentRequirements

        # Map V1 network to V2
        v1_network = payment_requirements.get("network", "")
        v2_network = V1_TO_V2_NETWORK_MAP.get(v1_network, v1_network)

        # Convert V1 maxAmountRequired to V2 amount
        max_amount = payment_requirements.get("maxAmountRequired", "0")

        # Build V2 requirements
        v2_requirements = PaymentRequirements(
            scheme=payment_requirements.get("scheme", "exact"),
            network=v2_network,
            amount=str(max_amount),
            pay_to=payment_requirements.get("payTo", ""),
            asset=payment_requirements.get("asset", ""),
            max_timeout_seconds=payment_requirements.get("maxTimeoutSeconds"),
            extra=payment_requirements.get("extra"),
        )

        # Create V2 payload
        return self._v2_scheme.create_payment_payload(v2_requirements)
