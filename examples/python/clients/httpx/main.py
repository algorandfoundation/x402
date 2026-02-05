"""x402 httpx client example - async HTTP with automatic payment handling."""

import asyncio
import os
import sys

from dotenv import load_dotenv
from eth_account import Account

from x402 import x402Client
from x402.http import x402HTTPClient
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact.register import register_exact_evm_client
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact.register import register_exact_svm_client
from x402.mechanisms.avm import AlgorandSigner
from x402.mechanisms.avm.exact.register import register_exact_avm_client

# Load environment variables
load_dotenv()


def validate_environment() -> tuple[str | None, str | None, str | None, str, str]:
    """Validate required environment variables.

    Returns:
        Tuple of (evm_private_key, svm_private_key, avm_mnemonic, base_url, endpoint_path).

    Raises:
        SystemExit: If required environment variables are missing.
    """
    evm_private_key = os.getenv("EVM_PRIVATE_KEY")
    svm_private_key = os.getenv("SVM_PRIVATE_KEY")
    avm_mnemonic = os.getenv("AVM_MNEMONIC")
    base_url = os.getenv("RESOURCE_SERVER_URL")
    endpoint_path = os.getenv("ENDPOINT_PATH")

    missing = []
    if not evm_private_key and not svm_private_key and not avm_mnemonic:
        missing.append("EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_MNEMONIC")
    if not base_url:
        missing.append("RESOURCE_SERVER_URL")
    if not endpoint_path:
        missing.append("ENDPOINT_PATH")

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("Please copy .env-local to .env and fill in the values.")
        sys.exit(1)

    return evm_private_key, svm_private_key, avm_mnemonic, base_url, endpoint_path


async def main() -> None:
    """Main entry point demonstrating httpx with x402 payments."""
    # Validate environment
    evm_private_key, svm_private_key, avm_mnemonic, base_url, endpoint_path = (
        validate_environment()
    )

    # Create x402 client
    client = x402Client()

    # Register EVM payment scheme if private key provided
    if evm_private_key:
        account = Account.from_key(evm_private_key)
        register_exact_evm_client(client, EthAccountSigner(account))
        print(f"Initialized EVM account: {account.address}")

    # Register SVM payment scheme if private key provided
    if svm_private_key:
        svm_signer = KeypairSigner.from_base58(svm_private_key)
        register_exact_svm_client(client, svm_signer)
        print(f"Initialized SVM account: {svm_signer.address}")

    # Register AVM (Algorand) payment scheme if mnemonic provided
    if avm_mnemonic:
        avm_signer = AlgorandSigner.from_mnemonic(avm_mnemonic)
        register_exact_avm_client(client, avm_signer)
        print(f"Initialized AVM account: {avm_signer.address}")

    # Create HTTP client helper for payment response extraction
    http_client = x402HTTPClient(client)

    # Build full URL
    url = f"{base_url}{endpoint_path}"
    print(f"Making request to: {url}\n")

    # Make request using async context manager
    # Use longer timeout for blockchain transactions (Algorand can take up to 4.5s per block)
    async with x402HttpxClient(client, timeout=60.0) as http:
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
