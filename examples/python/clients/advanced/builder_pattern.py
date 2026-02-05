"""Network-specific registration with builder pattern example.

Demonstrates how to configure the x402Client using the builder pattern,
chaining .register() calls to map network patterns to mechanism schemes.

Use this approach when you need:
- Different signers for different networks (e.g., separate keys for mainnet vs testnet)
- Fine-grained control over which networks are supported
- Custom scheme configurations per network
- Multi-chain support (EVM, SVM, AVM)
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from eth_account import Account

from x402 import x402Client
from x402.http import x402HTTPClient
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.mechanisms.avm import AlgorandSigner, ALGORAND_MAINNET_CAIP2, ALGORAND_TESTNET_CAIP2
from x402.mechanisms.avm.exact import ExactAvmScheme

load_dotenv()


async def run_builder_pattern_example(
    evm_private_key: str | None,
    svm_private_key: str | None,
    avm_mnemonic: str | None,
    url: str,
    mainnet_key: str | None = None,
    testnet_key: str | None = None,
) -> None:
    """Run the builder pattern example.

    Args:
        evm_private_key: Default EVM private key for signing (optional).
        svm_private_key: Solana private key for signing (optional, for future extension).
        avm_mnemonic: Algorand mnemonic for signing (optional).
        url: URL to make the request to.
        mainnet_key: Optional separate EVM key for mainnet (defaults to evm_private_key).
        testnet_key: Optional separate EVM key for testnet (defaults to evm_private_key).
    """
    if not evm_private_key and not avm_mnemonic:
        print("Error: At least one of EVM_PRIVATE_KEY or AVM_MNEMONIC is required")
        sys.exit(1)

    print("🔧 Creating client with builder pattern...\n")

    # Start building the client
    client = x402Client()

    # Register EVM networks if private key provided
    if evm_private_key:
        # Create accounts - in production, you might use different keys per network
        default_account = Account.from_key(evm_private_key)
        mainnet_account = Account.from_key(mainnet_key) if mainnet_key else default_account
        testnet_account = Account.from_key(testnet_key) if testnet_key else default_account

        # Create signers for different networks
        default_signer = EthAccountSigner(default_account)
        mainnet_signer = EthAccountSigner(mainnet_account)
        testnet_signer = EthAccountSigner(testnet_account)

        # Builder pattern allows fine-grained control over network registration
        # More specific patterns take precedence over wildcards
        client = (
            client
            # Wildcard: All EVM networks (fallback)
            .register("eip155:*", ExactEvmScheme(default_signer))
            # Specific: Ethereum mainnet with dedicated signer
            .register("eip155:1", ExactEvmScheme(mainnet_signer))
            # Specific: Base mainnet
            .register("eip155:8453", ExactEvmScheme(mainnet_signer))
            # Specific: Base Sepolia testnet with testnet signer
            .register("eip155:84532", ExactEvmScheme(testnet_signer))
            # Specific: Sepolia testnet
            .register("eip155:11155111", ExactEvmScheme(testnet_signer))
        )

        print("Registered EVM networks:")
        print(f"  - eip155:* (all EVM): {default_account.address}")
        print(f"  - eip155:1 (Ethereum mainnet): {mainnet_account.address}")
        print(f"  - eip155:8453 (Base mainnet): {mainnet_account.address}")
        print(f"  - eip155:84532 (Base Sepolia): {testnet_account.address}")
        print(f"  - eip155:11155111 (Sepolia): {testnet_account.address}")

    # Register AVM networks if mnemonic provided
    if avm_mnemonic:
        avm_signer = AlgorandSigner.from_mnemonic(avm_mnemonic)

        # Register Algorand networks - can use wildcards or specific networks
        client = (
            client
            # Wildcard: All Algorand networks (fallback)
            .register("algorand:*", ExactAvmScheme(avm_signer))
            # Specific: Algorand mainnet
            .register(ALGORAND_MAINNET_CAIP2, ExactAvmScheme(avm_signer))
            # Specific: Algorand testnet
            .register(ALGORAND_TESTNET_CAIP2, ExactAvmScheme(avm_signer))
        )

        print("Registered AVM networks:")
        print(f"  - algorand:* (all Algorand): {avm_signer.address}")
        print(f"  - {ALGORAND_MAINNET_CAIP2} (Algorand mainnet): {avm_signer.address}")
        print(f"  - {ALGORAND_TESTNET_CAIP2} (Algorand testnet): {avm_signer.address}")

    print()

    # Show registered schemes for debugging
    schemes = client.get_registered_schemes()
    print(f"Total registered schemes: {len(schemes.get(2, []))} (v2)")
    print()

    # Create HTTP client helper for payment response extraction
    http_client = x402HTTPClient(client)

    print(f"🌐 Making request to: {url}\n")

    async with x402HttpxClient(client) as http:
        response = await http.get(url)
        await response.aread()

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")

        if response.is_success:
            try:
                settle_response = http_client.get_payment_settle_response(
                    lambda name: response.headers.get(name)
                )
                print(
                    f"\n💰 Payment Details: {settle_response.model_dump_json(indent=2)}"
                )
            except ValueError:
                print("\nNo payment response header found")


async def main() -> None:
    """Main entry point."""
    evm_private_key = os.getenv("EVM_PRIVATE_KEY")
    svm_private_key = os.getenv("SVM_PRIVATE_KEY")
    avm_mnemonic = os.getenv("AVM_MNEMONIC")
    mainnet_key = os.getenv("MAINNET_PRIVATE_KEY")  # Optional: separate mainnet key
    testnet_key = os.getenv("TESTNET_PRIVATE_KEY")  # Optional: separate testnet key
    base_url = os.getenv("RESOURCE_SERVER_URL", "http://localhost:4021")
    endpoint_path = os.getenv("ENDPOINT_PATH", "/weather")

    if not evm_private_key and not avm_mnemonic:
        print("Error: At least one of EVM_PRIVATE_KEY or AVM_MNEMONIC is required")
        print("Please copy .env-local to .env and fill in the values.")
        sys.exit(1)

    url = f"{base_url}{endpoint_path}"
    await run_builder_pattern_example(
        evm_private_key, svm_private_key, avm_mnemonic, url, mainnet_key, testnet_key
    )


if __name__ == "__main__":
    asyncio.run(main())
