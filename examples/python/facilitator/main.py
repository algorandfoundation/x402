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
from x402.mechanisms.avm import FacilitatorAlgorandSigner, ALGORAND_TESTNET_CAIP2
from x402.mechanisms.avm.exact import register_exact_avm_facilitator

# Load environment variables
load_dotenv()

# Configuration
PORT = int(os.environ.get("PORT", "4022"))

# Check for at least one private key
evm_key = os.environ.get("EVM_PRIVATE_KEY")
svm_key = os.environ.get("SVM_PRIVATE_KEY")
avm_mnemonic = os.environ.get("AVM_MNEMONIC")

if not evm_key and not svm_key and not avm_mnemonic:
    print("Error: At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_MNEMONIC required")
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

# Register AVM (Algorand) scheme if mnemonic provided
if avm_mnemonic:
    avm_signer = FacilitatorAlgorandSigner(
        algod_url=os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud"),
        algod_token=os.environ.get("ALGOD_TOKEN", ""),
    )
    avm_signer.add_account_from_mnemonic(avm_mnemonic)
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
