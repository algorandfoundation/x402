"""Network-specific registration with builder pattern example.

Demonstrates how to configure the x402Client using the builder pattern,
chaining .register() calls to map network patterns to mechanism schemes.

Use this approach when you need:
- Different signers for different networks (e.g., separate keys for mainnet vs testnet)
- Fine-grained control over which networks are supported
- Custom scheme configurations per network
"""

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
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.mechanisms.svm import KeypairSigner, SOLANA_MAINNET_CAIP2, SOLANA_DEVNET_CAIP2
from x402.mechanisms.svm.exact import ExactSvmScheme
from x402.mechanisms.avm import ALGORAND_MAINNET_CAIP2, ALGORAND_TESTNET_CAIP2
from x402.mechanisms.avm.exact import ExactAvmScheme

load_dotenv()


async def run_builder_pattern_example(
    private_key: str,
    url: str,
    svm_private_key: str,
    avm_private_key: str,
    mainnet_key: str | None = None,
    testnet_key: str | None = None,
) -> None:
    """Run the builder pattern example.

    Args:
        private_key: Default EVM private key for signing.
        url: URL to make the request to.
        svm_private_key: Base58-encoded Solana private key.
        avm_private_key: Base64-encoded 64-byte Algorand private key.
        mainnet_key: Optional separate key for mainnet (defaults to private_key).
        testnet_key: Optional separate key for testnet (defaults to private_key).
    """
    print("🔧 Creating client with builder pattern...\n")

    # Create accounts - in production, you might use different keys per network
    default_account = Account.from_key(private_key)
    mainnet_account = Account.from_key(mainnet_key) if mainnet_key else default_account
    testnet_account = Account.from_key(testnet_key) if testnet_key else default_account

    # Create signers for different networks
    default_signer = EthAccountSigner(default_account)
    mainnet_signer = EthAccountSigner(mainnet_account)
    testnet_signer = EthAccountSigner(testnet_account)

    # Builder pattern allows fine-grained control over network registration
    # More specific patterns take precedence over wildcards
    client = (
        x402Client()
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

    # Register SVM (Solana) networks
    svm_signer = KeypairSigner.from_base58(svm_private_key)

    client = (
        client
        # Wildcard: All Solana networks (fallback)
        .register("solana:*", ExactSvmScheme(svm_signer))
        # Specific: Solana mainnet
        .register(SOLANA_MAINNET_CAIP2, ExactSvmScheme(svm_signer))
        # Specific: Solana devnet
        .register(SOLANA_DEVNET_CAIP2, ExactSvmScheme(svm_signer))
    )

    print("Registered SVM networks:")
    print(f"  - solana:* (all Solana): {svm_signer.address}")
    print(f"  - {SOLANA_MAINNET_CAIP2} (Solana mainnet): {svm_signer.address}")
    print(f"  - {SOLANA_DEVNET_CAIP2} (Solana devnet): {svm_signer.address}")

    # Register AVM (Algorand) networks
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
    private_key = os.getenv("EVM_PRIVATE_KEY")
    svm_private_key = os.getenv("SVM_PRIVATE_KEY")
    mainnet_key = os.getenv("MAINNET_PRIVATE_KEY")  # Optional: separate mainnet key
    testnet_key = os.getenv("TESTNET_PRIVATE_KEY")  # Optional: separate testnet key
    avm_private_key = os.getenv("AVM_PRIVATE_KEY")
    base_url = os.getenv("RESOURCE_SERVER_URL", "http://localhost:4021")
    endpoint_path = os.getenv("ENDPOINT_PATH", "/weather")

    missing = []
    if not private_key:
        missing.append("EVM_PRIVATE_KEY")
    if not svm_private_key:
        missing.append("SVM_PRIVATE_KEY")
    if not avm_private_key:
        missing.append("AVM_PRIVATE_KEY")

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("Please copy .env-local to .env and fill in the values.")
        sys.exit(1)

    url = f"{base_url}{endpoint_path}"
    await run_builder_pattern_example(
        private_key, url, svm_private_key, avm_private_key, mainnet_key, testnet_key
    )


if __name__ == "__main__":
    asyncio.run(main())
