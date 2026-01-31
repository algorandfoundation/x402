"""AVM client implementation for the Exact payment scheme (V2).

Creates atomic transaction groups for ASA payments, optionally with
fee abstraction (gasless transactions).
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

try:
    from algosdk import encoding, transaction
    from algosdk.v2client import algod

    ALGOSDK_AVAILABLE = True
except ImportError:
    ALGOSDK_AVAILABLE = False

from ....schemas import PaymentRequirements
from ..constants import NETWORK_CONFIGS, SCHEME_EXACT
from ..signer import ClientAvmSigner
from ..types import ExactAvmPayload
from ..utils import normalize_network

if TYPE_CHECKING:
    pass


def _check_algosdk() -> None:
    """Check that algosdk is available."""
    if not ALGOSDK_AVAILABLE:
        raise ImportError(
            "AVM mechanism requires py-algorand-sdk. Install with: pip install x402[avm]"
        )


class ExactAvmScheme:
    """AVM client implementation for the Exact payment scheme (V2).

    Implements SchemeNetworkClient protocol. Returns the inner payload dict,
    which x402Client wraps into a full PaymentPayload.

    Creates atomic transaction groups for ASA payments:
    - Without fee abstraction: Single ASA transfer transaction
    - With fee abstraction: [Fee payer txn (unsigned), ASA transfer (signed)]

    Attributes:
        scheme: The scheme identifier ("exact").
    """

    scheme = SCHEME_EXACT

    def __init__(self, signer: ClientAvmSigner, algod_url: str | None = None):
        """Create ExactAvmScheme.

        Args:
            signer: AVM signer for payment authorizations.
            algod_url: Optional custom Algod URL.
        """
        _check_algosdk()
        self._signer = signer
        self._custom_algod_url = algod_url
        self._clients: dict[str, algod.AlgodClient] = {}

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

        client = algod.AlgodClient("", algod_url)
        self._clients[caip2_network] = client
        return client

    def create_payment_payload(
        self,
        requirements: PaymentRequirements,
    ) -> dict[str, Any]:
        """Create atomic transaction group for payment.

        If feePayer in requirements.extra:
          - Creates 2-txn group: [fee_payer_txn (unsigned), asa_transfer (signed)]
          - Fee payer covers all fees (pooled: minFee * 2)
          - Client signs only ASA transfer

        Else:
          - Creates single ASA transfer with normal fee
          - Client signs the transaction

        Args:
            requirements: Payment requirements from server.

        Returns:
            Inner payload dict (paymentGroup, paymentIndex).
            x402Client wraps this with x402_version, accepted, resource, extensions.

        Raises:
            ValueError: If network is unsupported.
        """
        network = str(requirements.network)
        client = self._get_client(network)

        # Get suggested params
        sp = client.suggested_params()

        # Check for fee abstraction
        extra = requirements.extra or {}
        fee_payer = extra.get("feePayer")

        transactions: list[transaction.Transaction] = []
        payment_index: int

        if fee_payer:
            # === Fee Abstraction Mode ===
            # Fee payer transaction: self-payment with pooled fees
            total_txn_count = 2
            min_fee = sp.min_fee or 1000
            pooled_fee = min_fee * total_txn_count

            # Create suggested params for fee payer (with pooled fee)
            fee_payer_sp = transaction.SuggestedParams(
                fee=pooled_fee,
                flat_fee=True,  # CRITICAL: Prevent fee recalculation
                first=sp.first,
                last=sp.last,
                gh=sp.gh,
                gen=sp.gen,
                min_fee=sp.min_fee,
            )

            fee_payer_txn = transaction.PaymentTxn(
                sender=fee_payer,
                sp=fee_payer_sp,
                receiver=fee_payer,  # Self-payment
                amt=0,
                note=b"x402-fee-payer",
            )
            transactions.append(fee_payer_txn)

            # ASA transfer with zero fee (fee payer covers)
            asset_sp = transaction.SuggestedParams(
                fee=0,
                flat_fee=True,  # CRITICAL: Prevent fee recalculation
                first=sp.first,
                last=sp.last,
                gh=sp.gh,
                gen=sp.gen,
                min_fee=sp.min_fee,
            )

            # Payment index is the ASA transfer (index 1 in group)
            payment_index = 1
        else:
            # === Normal Mode ===
            asset_sp = sp
            # Payment index is 0 (single transaction)
            payment_index = 0

        # Create ASA transfer transaction
        asa_transfer = transaction.AssetTransferTxn(
            sender=self._signer.address,
            sp=asset_sp,
            receiver=requirements.pay_to,
            amt=int(requirements.amount),
            index=int(requirements.asset),
            note=b"x402-payment",
        )
        transactions.append(asa_transfer)

        # Assign group ID if multiple transactions
        if len(transactions) > 1:
            transactions = transaction.assign_group_id(transactions)

        # Determine which transactions client should sign
        # (all transactions where sender is client's address)
        client_indexes = [
            i
            for i, txn in enumerate(transactions)
            if encoding.encode_address(txn.sender) == self._signer.address
        ]

        # Get unsigned transaction bytes (dictify format for signing)
        unsigned_bytes_list: list[bytes] = []
        for txn in transactions:
            # Encode as msgpack dict format
            txn_dict = txn.dictify()
            unsigned_bytes_list.append(encoding.msgpack_encode(txn_dict))

        # Sign client's transactions
        signed_results = self._signer.sign_transactions(unsigned_bytes_list, client_indexes)

        # Build payment group: signed where applicable, unsigned for fee payer
        payment_group: list[str] = []
        for i, txn_bytes in enumerate(unsigned_bytes_list):
            signed = signed_results[i]
            if signed:
                # Use signed transaction
                payment_group.append(base64.b64encode(signed).decode("utf-8"))
            else:
                # Use unsigned transaction (fee payer will sign)
                payment_group.append(base64.b64encode(txn_bytes).decode("utf-8"))

        payload = ExactAvmPayload(
            payment_group=payment_group,
            payment_index=payment_index,
        )

        return payload.to_dict()
