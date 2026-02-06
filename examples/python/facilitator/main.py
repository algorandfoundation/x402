"""x402 Facilitator Example.

FastAPI-based facilitator service that verifies and settles payments
on-chain for the x402 protocol.

Supports:
- EVM networks (Base Sepolia) via web3.py
- SVM networks (Solana Devnet) via solders
- AVM networks (Algorand Testnet) via py-algorand-sdk

Run with: uvicorn main:app --port 4022
"""

import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from x402 import x402Facilitator
from x402.mechanisms.evm import FacilitatorWeb3Signer
from x402.mechanisms.evm.exact import register_exact_evm_facilitator
from x402.mechanisms.svm import FacilitatorKeypairSigner
from x402.mechanisms.svm.exact import register_exact_svm_facilitator
from x402.mechanisms.avm import ALGORAND_TESTNET_CAIP2
from x402.mechanisms.avm.exact import register_exact_avm_facilitator

# Load environment variables
load_dotenv()

# Configuration
PORT = int(os.environ.get("PORT", "4022"))

# Check for at least one private key
evm_key = os.environ.get("EVM_PRIVATE_KEY")
svm_key = os.environ.get("SVM_PRIVATE_KEY")
avm_private_key = os.environ.get("AVM_PRIVATE_KEY")

if not evm_key and not svm_key and not avm_private_key:
    print("Error: At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_PRIVATE_KEY required")
    sys.exit(1)


# Async hook functions for the facilitator
async def before_verify_hook(ctx):
    print(f"Before verify: {ctx.payment_payload}")


async def after_verify_hook(ctx):
    print(f"After verify: {ctx.result}")


async def verify_failure_hook(ctx):
    print(f"Verify failure: {ctx.error}")


async def before_settle_hook(ctx):
    print(f"Before settle: {ctx.payment_payload}")


async def after_settle_hook(ctx):
    print(f"After settle: {ctx.result}")


async def settle_failure_hook(ctx):
    print(f"Settle failure: {ctx.error}")


# Initialize the x402 Facilitator
facilitator = (
    x402Facilitator()
    .on_before_verify(before_verify_hook)
    .on_after_verify(after_verify_hook)
    .on_verify_failure(verify_failure_hook)
    .on_before_settle(before_settle_hook)
    .on_after_settle(after_settle_hook)
    .on_settle_failure(settle_failure_hook)
)

# Register EVM scheme if private key provided
if evm_key:
    evm_signer = FacilitatorWeb3Signer(
        private_key=evm_key,
        rpc_url=os.environ.get("EVM_RPC_URL", "https://sepolia.base.org"),
    )
    print(f"EVM Facilitator account: {evm_signer.get_addresses()[0]}")
    register_exact_evm_facilitator(
        facilitator,
        evm_signer,
        networks="eip155:84532",  # Base Sepolia
        deploy_erc4337_with_eip6492=True,
    )

# Register SVM scheme if private key provided
if svm_key:
    from solders.keypair import Keypair

    svm_keypair = Keypair.from_base58_string(svm_key)
    svm_signer = FacilitatorKeypairSigner(svm_keypair)
    print(f"SVM Facilitator account: {svm_signer.get_addresses()[0]}")
    register_exact_svm_facilitator(
        facilitator,
        svm_signer,
        networks="solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",  # Devnet
    )

# Register AVM (Algorand) scheme if private key provided
if avm_private_key:
    import base64
    import algosdk

    # Decode Base64 private key (64 bytes: 32-byte seed + 32-byte public key)
    secret_key = base64.b64decode(avm_private_key)
    if len(secret_key) != 64:
        print("Error: AVM_PRIVATE_KEY must be a Base64-encoded 64-byte key")
        sys.exit(1)
    avm_address = algosdk.encoding.encode_address(secret_key[32:])

    # Create Algod client for testnet
    algod_url = os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    algod_token = os.environ.get("ALGOD_TOKEN", "")
    algod_client = algosdk.v2client.algod.AlgodClient(algod_token, algod_url)

    # Implement FacilitatorAvmSigner interface directly
    class AlgorandFacilitatorSigner:
        def __init__(self, sk: bytes, addr: str, client):
            self._secret_key = sk
            self._address = addr
            self._algod = client

        def get_addresses(self) -> list[str]:
            return [self._address]

        def sign_transaction(self, txn_bytes: bytes, fee_payer: str, network: str) -> bytes:
            if fee_payer != self._address:
                raise ValueError(f"Unknown fee payer: {fee_payer}")
            # algosdk Python API uses base64 strings; SDK protocol uses raw bytes
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
            from algosdk.v2client.models import SimulateRequest, SimulateRequestTransactionGroup
            decoded_txns = []
            for txn_bytes in group_bytes:
                b64 = base64.b64encode(txn_bytes).decode()
                obj = algosdk.encoding.msgpack_decode(b64)
                if isinstance(obj, algosdk.transaction.SignedTransaction):
                    decoded_txns.append(obj)
                else:
                    # Wrap unsigned transaction for simulation
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
                raise Exception(f"Simulation failed: {result['txn-groups'][0]['failure-message']}")

        def send_group(self, group_bytes: list[bytes], network: str) -> str:
            # Send raw bytes directly (like TS sendRawTransaction) to
            # avoid the decode/re-encode round-trip in send_transactions
            raw_group = b"".join(group_bytes)
            txid = self._algod.send_raw_transaction(
                base64.b64encode(raw_group)
            )
            return txid

        def confirm_transaction(self, txid: str, network: str, rounds: int = 4) -> None:
            algosdk.transaction.wait_for_confirmation(self._algod, txid, rounds)

    avm_signer = AlgorandFacilitatorSigner(secret_key, avm_address, algod_client)
    print(f"AVM Facilitator account: {avm_signer.get_addresses()[0]}")
    register_exact_avm_facilitator(
        facilitator,
        avm_signer,
        networks=ALGORAND_TESTNET_CAIP2,  # Algorand Testnet
    )


# Pydantic models for request/response
class VerifyRequest(BaseModel):
    """Verify endpoint request body."""

    paymentPayload: dict
    paymentRequirements: dict


class SettleRequest(BaseModel):
    """Settle endpoint request body."""

    paymentPayload: dict
    paymentRequirements: dict


# Initialize FastAPI app
app = FastAPI(
    title="x402 Facilitator",
    description="Verifies and settles x402 payments on-chain",
    version="2.0.0",
)


@app.post("/verify")
async def verify(request: VerifyRequest):
    """Verify a payment against requirements.

    Args:
        request: Payment payload and requirements to verify.

    Returns:
        VerifyResponse with isValid and payer (if valid) or invalidReason.
    """
    try:
        from x402.schemas import PaymentRequirements, parse_payment_payload

        # Parse payload (auto-detects V1/V2) and requirements
        payload = parse_payment_payload(request.paymentPayload)
        requirements = PaymentRequirements.model_validate(request.paymentRequirements)

        # Verify payment (await async method)
        response = await facilitator.verify(payload, requirements)

        return {
            "isValid": response.is_valid,
            "payer": response.payer,
            "invalidReason": response.invalid_reason,
        }
    except Exception as e:
        print(f"Verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settle")
async def settle(request: SettleRequest):
    """Settle a payment on-chain.

    Args:
        request: Payment payload and requirements to settle.

    Returns:
        SettleResponse with success, transaction, network, and payer.
    """
    try:
        from x402.schemas import PaymentRequirements, parse_payment_payload

        # Parse payload (auto-detects V1/V2) and requirements
        payload = parse_payment_payload(request.paymentPayload)
        requirements = PaymentRequirements.model_validate(request.paymentRequirements)

        # Settle payment (await async method)
        response = await facilitator.settle(payload, requirements)

        return {
            "success": response.success,
            "transaction": response.transaction,
            "network": response.network,
            "payer": response.payer,
            "errorReason": response.error_reason,
        }
    except Exception as e:
        print(f"Settle error: {e}")

        # Check if this was an abort from hook
        if "aborted" in str(e).lower():
            return {
                "success": False,
                "errorReason": str(e),
                "network": request.paymentPayload.get("accepted", {}).get("network", "unknown"),
                "transaction": "",
            }

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/supported")
async def supported():
    """Get supported payment kinds and extensions.

    Returns:
        SupportedResponse with kinds, extensions, and signers.
    """
    try:
        response = facilitator.get_supported()

        return {
            "kinds": [
                {
                    "x402Version": k.x402_version,
                    "scheme": k.scheme,
                    "network": k.network,
                    "extra": k.extra,
                }
                for k in response.kinds
            ],
            "extensions": response.extensions,
            "signers": response.signers,
        }
    except Exception as e:
        print(f"Supported error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    print(f"Facilitator listening on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
