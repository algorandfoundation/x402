"""V1 facilitator implementation for AVM exact payment scheme.

Provides backward compatibility for V1 protocol by wrapping the V2 implementation.
Maps V1 network names (algorand-mainnet, algorand-testnet) to V2 CAIP-2 identifiers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...constants import V1_TO_V2_NETWORK_MAP, V2_TO_V1_NETWORK_MAP

if TYPE_CHECKING:
    from ...signer import FacilitatorAvmSigner


class ExactAvmSchemeV1:
    """V1 facilitator implementation for AVM exact payment scheme.

    Wraps V2 ExactAvmScheme with V1 network name support and
    field name mapping.

    This implements SchemeNetworkFacilitatorV1 protocol.

    Attributes:
        scheme: The scheme identifier ("exact").
    """

    scheme = "exact"

    def __init__(self, signer: "FacilitatorAvmSigner"):
        """Create ExactAvmSchemeV1.

        Args:
            signer: AVM signer for verification/settlement.
        """
        # Import here to avoid circular imports
        from ..facilitator import ExactAvmScheme

        self._v2_scheme = ExactAvmScheme(signer)

    def get_signers(self, network: str) -> list[str]:
        """Get facilitator wallet addresses.

        Args:
            network: V1 network name.

        Returns:
            List of facilitator fee payer addresses.
        """
        v2_network = V1_TO_V2_NETWORK_MAP.get(network, network)
        return self._v2_scheme.get_signers(v2_network)

    def verify(
        self,
        payload: dict[str, Any],
        payment_requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify payment payload for V1 protocol.

        Args:
            payload: V1 payment payload dict.
            payment_requirements: V1 payment requirements dict.

        Returns:
            V1 verify response dict.
        """
        # Import types for conversion
        from .....schemas import PaymentPayload, PaymentRequirements

        # Convert V1 to V2 network
        v1_network = payment_requirements.get("network", "")
        v2_network = V1_TO_V2_NETWORK_MAP.get(v1_network, v1_network)

        # Build V2 requirements
        v2_requirements = PaymentRequirements(
            scheme=payment_requirements.get("scheme", "exact"),
            network=v2_network,
            amount=str(payment_requirements.get("maxAmountRequired", "0")),
            pay_to=payment_requirements.get("payTo", ""),
            asset=payment_requirements.get("asset", ""),
            max_timeout_seconds=payment_requirements.get("maxTimeoutSeconds"),
            extra=payment_requirements.get("extra"),
        )

        # Build V2 accepted requirements
        v2_accepted = PaymentRequirements(
            scheme=payload.get("scheme", "exact"),
            network=v2_network,
            amount=str(payload.get("maxAmountRequired", "0")),
            pay_to=payload.get("payTo", ""),
            asset=payload.get("asset", ""),
            max_timeout_seconds=payload.get("maxTimeoutSeconds"),
            extra=payload.get("extra"),
        )

        # Build V2 payload
        v2_payload = PaymentPayload(
            x402_version=1,
            scheme=payload.get("scheme", "exact"),
            network=v2_network,
            payload=payload.get("payload", {}),
            accepted=v2_accepted,
            resource=payload.get("resource"),
            extensions={},
            output_schema=None,
        )

        # Call V2 verify
        result = self._v2_scheme.verify(v2_payload, v2_requirements)

        # Convert response to V1 format
        return {
            "isValid": result.is_valid,
            "invalidReason": result.invalid_reason,
            "payer": result.payer,
        }

    def settle(
        self,
        payload: dict[str, Any],
        payment_requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Settle payment for V1 protocol.

        Args:
            payload: V1 payment payload dict.
            payment_requirements: V1 payment requirements dict.

        Returns:
            V1 settle response dict.
        """
        # Import types for conversion
        from .....schemas import PaymentPayload, PaymentRequirements

        # Convert V1 to V2 network
        v1_network = payment_requirements.get("network", "")
        v2_network = V1_TO_V2_NETWORK_MAP.get(v1_network, v1_network)

        # Build V2 requirements
        v2_requirements = PaymentRequirements(
            scheme=payment_requirements.get("scheme", "exact"),
            network=v2_network,
            amount=str(payment_requirements.get("maxAmountRequired", "0")),
            pay_to=payment_requirements.get("payTo", ""),
            asset=payment_requirements.get("asset", ""),
            max_timeout_seconds=payment_requirements.get("maxTimeoutSeconds"),
            extra=payment_requirements.get("extra"),
        )

        # Build V2 accepted requirements
        v2_accepted = PaymentRequirements(
            scheme=payload.get("scheme", "exact"),
            network=v2_network,
            amount=str(payload.get("maxAmountRequired", "0")),
            pay_to=payload.get("payTo", ""),
            asset=payload.get("asset", ""),
            max_timeout_seconds=payload.get("maxTimeoutSeconds"),
            extra=payload.get("extra"),
        )

        # Build V2 payload
        v2_payload = PaymentPayload(
            x402_version=1,
            scheme=payload.get("scheme", "exact"),
            network=v2_network,
            payload=payload.get("payload", {}),
            accepted=v2_accepted,
            resource=payload.get("resource"),
            extensions={},
            output_schema=None,
        )

        # Call V2 settle
        result = self._v2_scheme.settle(v2_payload, v2_requirements)

        # Convert network back to V1 if needed
        response_network = result.network
        if response_network in V2_TO_V1_NETWORK_MAP:
            response_network = V2_TO_V1_NETWORK_MAP[response_network]

        # Convert response to V1 format
        return {
            "success": result.success,
            "errorReason": result.error_reason,
            "transaction": result.transaction,
            "network": response_network,
            "payer": result.payer,
        }
