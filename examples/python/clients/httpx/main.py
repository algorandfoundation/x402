"""x402 httpx client example - async HTTP with automatic payment handling."""

import asyncio
import base64
import os
import sys

import algosdk
from dotenv import load_dotenv
from eth_account import Account

from x402 import x402Client
from x402.http import x402HTTPClient
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact.register import register_exact_evm_client
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client
from x402.mechanisms.avm.exact.register import register_exact_avm_client

# Load environment variables
load_dotenv()


def validate_environment() -> tuple[str, str, str, str, str]:
    """Validate required environment variables.

    Returns:
        Tuple of (evm_private_key, svm_private_key, base_url, endpoint_path, avm_private_key).

    Raises:
        SystemExit: If required environment variables are missing.
    """
    evm_private_key = os.getenv("EVM_PRIVATE_KEY")
    svm_private_key = os.getenv("SVM_PRIVATE_KEY")
    avm_private_key = os.getenv("AVM_PRIVATE_KEY")
    base_url = os.getenv("RESOURCE_SERVER_URL")
    endpoint_path = os.getenv("ENDPOINT_PATH")

    missing = []
    if not evm_private_key:
        missing.append("EVM_PRIVATE_KEY")
    if not svm_private_key:
        missing.append("SVM_PRIVATE_KEY")
    if not avm_private_key:
        missing.append("AVM_PRIVATE_KEY")
    if not base_url:
        missing.append("RESOURCE_SERVER_URL")
    if not endpoint_path:
        missing.append("ENDPOINT_PATH")

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("Please copy .env-local to .env and fill in the values.")
        sys.exit(1)

    return evm_private_key, svm_private_key, base_url, endpoint_path, avm_private_key


async def main() -> None:
    """Main entry point demonstrating httpx with x402 payments."""
    # Validate environment
    evm_private_key, svm_private_key, base_url, endpoint_path, avm_private_key = (
        validate_environment()
    )

    # Create x402 client
    client = x402Client()

    # Register EVM payment scheme
    account = Account.from_key(evm_private_key)
    register_exact_evm_client(client, EthAccountSigner(account))
    print(f"Initialized EVM account: {account.address}")

    # Register SVM payment scheme
    svm_signer = KeypairSigner.from_base58(svm_private_key)
    register_exact_svm_client(client, svm_signer)
    print(f"Initialized SVM account: {svm_signer.address}")

    # Register AVM (Algorand) payment scheme
    # Decode Base64 private key (64 bytes: 32-byte seed + 32-byte public key)
    secret_key = base64.b64decode(avm_private_key)
    if len(secret_key) != 64:
        raise ValueError("AVM_PRIVATE_KEY must be a Base64-encoded 64-byte key")
    avm_address = algosdk.encoding.encode_address(secret_key[32:])

    # Implement ClientAvmSigner interface directly
    class AlgorandSigner:
        def __init__(self, sk: bytes, addr: str):
            self._secret_key = sk
            self._address = addr

        @property
        def address(self) -> str:
            return self._address

        def sign_transactions(
            self,
            unsigned_txns: list[bytes],
            indexes_to_sign: list[int],
        ) -> list[bytes | None]:
            # algosdk Python API uses base64 strings, but the SDK protocol
            # passes raw msgpack bytes. Convert at the boundary.
            sk_b64 = base64.b64encode(self._secret_key).decode()
            result = []
            for i, txn_bytes in enumerate(unsigned_txns):
                if i in indexes_to_sign:
                    txn = algosdk.encoding.msgpack_decode(
                        base64.b64encode(txn_bytes).decode()
                    )
                    signed = txn.sign(sk_b64)
                    result.append(
                        base64.b64decode(algosdk.encoding.msgpack_encode(signed))
                    )
                else:
                    result.append(None)
            return result

    avm_signer = AlgorandSigner(secret_key, avm_address)
    register_exact_avm_client(client, avm_signer)
    print(f"Initialized AVM account: {avm_address}")

    # Create HTTP client helper for payment response extraction
    http_client = x402HTTPClient(client)

    # Build full URL
    url = f"{base_url}{endpoint_path}"
    print(f"Making request to: {url}\n")

    # Make request using async context manager
    async with x402HttpxClient(client) as http:
        response = await http.get(url)
        await response.aread()

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")

        # Extract and print payment response if present
        if response.is_success:
            try:
                settle_response = http_client.get_payment_settle_response(
                    lambda name: response.headers.get(name)
                )
                print(
                    f"\nPayment response: {settle_response.model_dump_json(indent=2)}"
                )
            except ValueError:
                print("\nNo payment response header found")
        else:
            print(f"\nRequest failed (status: {response.status_code})")


if __name__ == "__main__":
    asyncio.run(main())
