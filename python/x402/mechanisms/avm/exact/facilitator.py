"""AVM facilitator implementation for the Exact payment scheme (V2).

Verifies and settles ASA payments on Algorand networks.
"""

from __future__ import annotations

import base64
import random
from typing import Any

from ....schemas import (
    Network,
    PaymentPayload,
    PaymentRequirements,
    SettleResponse,
    VerifyResponse,
)
from ..constants import (
    ERR_AMOUNT_INSUFFICIENT,
    ERR_EMPTY_GROUP,
    ERR_FEE_PAYER_MISSING,
    ERR_FEE_PAYER_NOT_MANAGED,
    ERR_FEE_PAYER_TRANSFERRING,
    ERR_GENESIS_HASH_MISMATCH,
    ERR_GROUP_DECODE_FAILED,
    ERR_GROUP_TOO_LARGE,
    ERR_INVALID_ASSET_ID,
    ERR_INVALID_GROUP_ID,
    ERR_INVALID_PAYMENT_INDEX,
    ERR_MISSING_GROUP_ID,
    ERR_MISSING_SIGNATURE,
    ERR_NETWORK_MISMATCH,
    ERR_RECIPIENT_MISMATCH,
    ERR_SIMULATION_FAILED,
    ERR_TRANSACTION_FAILED,
    ERR_UNSUPPORTED_SCHEME,
    MAX_GROUP_SIZE,
    SCHEME_EXACT,
    TXN_TYPE_ASSET_TRANSFER,
)
from ..signer import FacilitatorAvmSigner
from ..types import DecodedTransactionInfo, ExactAvmPayload
from ..utils import (
    decode_base64_transaction,
    get_genesis_hash,
    normalize_network,
    validate_fee_payer_transaction,
    validate_no_security_risks,
)


class ExactAvmScheme:
    """AVM facilitator implementation for the Exact payment scheme (V2).

    Verifies and settles ASA payments on Algorand networks.

    Attributes:
        scheme: The scheme identifier ("exact").
        caip_family: The CAIP family pattern ("algorand:*").
    """

    scheme = SCHEME_EXACT
    caip_family = "algorand:*"

    def __init__(self, signer: FacilitatorAvmSigner):
        """Create ExactAvmScheme facilitator.

        Args:
            signer: AVM signer for verification and settlement.
        """
        self._signer = signer

    def get_extra(self, network: Network) -> dict[str, Any] | None:
        """Get mechanism-specific extra data for the supported kinds endpoint.

        For AVM, this includes a randomly selected fee payer address.
        Random selection distributes load across multiple signers.

        Args:
            network: Network identifier (used for validation only).

        Returns:
            Extra data with feePayer address, or None if no signers.
        """
        _ = network  # Validated elsewhere
        addresses = self._signer.get_addresses()
        if not addresses:
            return None

        # Randomly select from available signers to distribute load
        fee_payer = random.choice(addresses)

        return {"feePayer": fee_payer}

    def get_signers(self, network: Network) -> list[str]:
        """Get facilitator wallet addresses.

        Args:
            network: Network identifier.

        Returns:
            List of facilitator fee payer addresses.
        """
        _ = network  # Unused
        return list(self._signer.get_addresses())

    def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """Verify ASA payment payload.

        Validates per Algorand exact scheme spec:
        1. Check paymentGroup contains 16 or fewer elements
        2. Decode all transactions from the paymentGroup
        3. Locate payment transaction (paymentIndex):
           - Check aamt (asset amount) >= requirements.amount
           - Check arcv (asset receiver) matches requirements.payTo
        4. If feePayer in requirements:
           - Locate fee payer transaction
           - Check type is "pay"
           - Check close, rekey, amt are omitted/zero
           - Check fee is reasonable
           - Sign the transaction
        5. Simulate group to verify it would succeed

        Security checks:
        - No rekey operations allowed
        - No close-to operations allowed
        - keyreg transactions blocked
        - Facilitator signers cannot transfer their own funds

        Args:
            payload: Payment payload from client.
            requirements: Payment requirements.

        Returns:
            VerifyResponse with is_valid and payer.
        """
        avm_payload = ExactAvmPayload.from_dict(payload.payload)
        network = str(requirements.network)
        caip2_network = normalize_network(network)

        # Step 1: Validate scheme and network
        if payload.accepted.scheme != SCHEME_EXACT or requirements.scheme != SCHEME_EXACT:
            return VerifyResponse(is_valid=False, invalid_reason=ERR_UNSUPPORTED_SCHEME, payer="")

        if str(payload.accepted.network) != str(requirements.network):
            return VerifyResponse(is_valid=False, invalid_reason=ERR_NETWORK_MISMATCH, payer="")

        # Step 2: Validate group size
        payment_group = avm_payload.payment_group
        payment_index = avm_payload.payment_index

        if not payment_group:
            return VerifyResponse(is_valid=False, invalid_reason=ERR_EMPTY_GROUP, payer="")

        if len(payment_group) > MAX_GROUP_SIZE:
            return VerifyResponse(is_valid=False, invalid_reason=ERR_GROUP_TOO_LARGE, payer="")

        if payment_index < 0 or payment_index >= len(payment_group):
            return VerifyResponse(is_valid=False, invalid_reason=ERR_INVALID_PAYMENT_INDEX, payer="")

        # Step 3: Decode all transactions
        decoded_txns: list[DecodedTransactionInfo] = []
        try:
            for b64_txn in payment_group:
                txn_info = decode_base64_transaction(b64_txn)
                decoded_txns.append(txn_info)
        except Exception as e:
            return VerifyResponse(
                is_valid=False,
                invalid_reason=ERR_GROUP_DECODE_FAILED,
                invalid_message=str(e),
                payer="",
            )

        # Step 4: Validate group IDs match (if multiple transactions)
        if len(decoded_txns) > 1:
            first_group_id = decoded_txns[0].group
            if not first_group_id:
                return VerifyResponse(
                    is_valid=False, invalid_reason=ERR_MISSING_GROUP_ID, payer=""
                )
            for txn_info in decoded_txns[1:]:
                if txn_info.group != first_group_id:
                    return VerifyResponse(
                        is_valid=False, invalid_reason=ERR_INVALID_GROUP_ID, payer=""
                    )

        # Step 5: Validate genesis hash matches network
        expected_genesis_hash = get_genesis_hash(caip2_network)
        for txn_info in decoded_txns:
            if txn_info.genesis_hash != expected_genesis_hash:
                return VerifyResponse(
                    is_valid=False, invalid_reason=ERR_GENESIS_HASH_MISMATCH, payer=""
                )

        # Step 6: Security checks on all transactions
        for txn_info in decoded_txns:
            security_error = validate_no_security_risks(txn_info)
            if security_error:
                return VerifyResponse(
                    is_valid=False, invalid_reason=security_error, payer=""
                )

        # Step 7: Verify payment transaction
        payment_txn = decoded_txns[payment_index]
        payer = payment_txn.sender

        # Payment must be asset transfer
        if payment_txn.type != TXN_TYPE_ASSET_TRANSFER:
            return VerifyResponse(
                is_valid=False,
                invalid_reason=ERR_INVALID_ASSET_ID,
                invalid_message="Payment transaction must be asset transfer (axfer)",
                payer=payer,
            )

        # Verify ASA ID matches
        required_asset = int(requirements.asset)
        if payment_txn.asset_index != required_asset:
            return VerifyResponse(
                is_valid=False, invalid_reason=ERR_INVALID_ASSET_ID, payer=payer
            )

        # Verify receiver matches payTo
        if payment_txn.asset_receiver != requirements.pay_to:
            return VerifyResponse(
                is_valid=False, invalid_reason=ERR_RECIPIENT_MISMATCH, payer=payer
            )

        # Verify amount is sufficient
        required_amount = int(requirements.amount)
        actual_amount = payment_txn.asset_amount or 0
        if actual_amount < required_amount:
            return VerifyResponse(
                is_valid=False, invalid_reason=ERR_AMOUNT_INSUFFICIENT, payer=payer
            )

        # Verify payment transaction is signed
        if not payment_txn.is_signed:
            return VerifyResponse(
                is_valid=False, invalid_reason=ERR_MISSING_SIGNATURE, payer=payer
            )

        # Step 8: Check for fee payer and validate if present
        extra = requirements.extra or {}
        fee_payer_str = extra.get("feePayer")

        signer_addresses = self._signer.get_addresses()

        # SECURITY: Verify facilitator's signers are not transferring their own funds
        if payment_txn.sender in signer_addresses:
            return VerifyResponse(
                is_valid=False, invalid_reason=ERR_FEE_PAYER_TRANSFERRING, payer=payer
            )

        fee_payer_index: int | None = None
        if fee_payer_str:
            # Verify that the requested feePayer is managed by this facilitator
            if fee_payer_str not in signer_addresses:
                return VerifyResponse(
                    is_valid=False, invalid_reason=ERR_FEE_PAYER_NOT_MANAGED, payer=payer
                )

            # Find fee payer transaction in group
            for i, txn_info in enumerate(decoded_txns):
                if txn_info.sender == fee_payer_str:
                    fee_payer_index = i
                    break

            if fee_payer_index is None:
                return VerifyResponse(
                    is_valid=False, invalid_reason=ERR_FEE_PAYER_MISSING, payer=payer
                )

            # Validate fee payer transaction
            fee_payer_txn = decoded_txns[fee_payer_index]
            fee_payer_error = validate_fee_payer_transaction(fee_payer_txn, fee_payer_str)
            if fee_payer_error:
                return VerifyResponse(
                    is_valid=False, invalid_reason=fee_payer_error, payer=payer
                )

        # Step 9: Sign fee payer transaction and simulate
        try:
            # Prepare group bytes
            group_bytes = [base64.b64decode(b64_txn) for b64_txn in payment_group]

            # Sign fee payer transaction if present
            if fee_payer_str and fee_payer_index is not None:
                group_bytes = self._signer.sign_group(
                    group_bytes, fee_payer_str, [fee_payer_index], caip2_network
                )

            # Simulate to verify transaction would succeed
            self._signer.simulate_group(group_bytes, caip2_network)

        except Exception as e:
            return VerifyResponse(
                is_valid=False,
                invalid_reason=ERR_SIMULATION_FAILED,
                invalid_message=str(e),
                payer=payer,
            )

        return VerifyResponse(is_valid=True, payer=payer)

    def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """Settle ASA payment on-chain.

        - Re-verifies payment
        - Signs fee payer transaction
        - Sends transaction group to network
        - Waits for confirmation (instant finality)

        Args:
            payload: Verified payment payload.
            requirements: Payment requirements.

        Returns:
            SettleResponse with success, transaction, and payer.
        """
        avm_payload = ExactAvmPayload.from_dict(payload.payload)
        network = str(payload.accepted.network)
        caip2_network = normalize_network(network)

        # First verify
        verify_result = self.verify(payload, requirements)
        if not verify_result.is_valid:
            return SettleResponse(
                success=False,
                error_reason=verify_result.invalid_reason,
                error_message=verify_result.invalid_message,
                network=network,
                payer=verify_result.payer,
                transaction="",
            )

        txid = ""
        try:
            # Prepare group bytes
            group_bytes = [base64.b64decode(b64_txn) for b64_txn in avm_payload.payment_group]

            # Sign fee payer transaction if present
            extra = requirements.extra or {}
            fee_payer_str = extra.get("feePayer")

            if fee_payer_str:
                # Find fee payer index
                decoded_txns: list[DecodedTransactionInfo] = []
                for b64_txn in avm_payload.payment_group:
                    txn_info = decode_base64_transaction(b64_txn)
                    decoded_txns.append(txn_info)

                fee_payer_index: int | None = None
                for i, txn_info in enumerate(decoded_txns):
                    if txn_info.sender == fee_payer_str:
                        fee_payer_index = i
                        break

                if fee_payer_index is not None:
                    group_bytes = self._signer.sign_group(
                        group_bytes, fee_payer_str, [fee_payer_index], caip2_network
                    )

            # Send transaction group to network
            txid = self._signer.send_group(group_bytes, caip2_network)

            # Wait for confirmation (instant finality)
            self._signer.confirm_transaction(txid, caip2_network)

            return SettleResponse(
                success=True,
                transaction=txid,
                network=network,
                payer=verify_result.payer,
            )

        except Exception as e:
            return SettleResponse(
                success=False,
                error_reason=ERR_TRANSACTION_FAILED,
                error_message=str(e),
                transaction=txid,
                network=network,
                payer=verify_result.payer or "",
            )
