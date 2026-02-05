#!/usr/bin/env python3
"""Advanced x402 client examples - main entry point.

This module provides a CLI to run different advanced examples demonstrating
various x402 client features including hooks, custom selectors, and builder patterns.

Usage:
    python index.py [example_name]

Examples:
    python index.py hooks              # Payment lifecycle hooks
    python index.py preferred_network  # Custom network selection
    python index.py builder_pattern    # Network-specific registration
    python index.py all                # Run all examples
"""

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


EXAMPLES = {
    "hooks": "Payment lifecycle hooks - before, after, failure callbacks",
    "preferred_network": "Custom network preference selector",
    "builder_pattern": "Network-specific registration with builder pattern",
}


def validate_environment() -> tuple[str | None, str | None, str | None, str]:
    """Validate required environment variables.

    Returns:
        Tuple of (evm_private_key, svm_private_key, avm_mnemonic, url).

    Raises:
        SystemExit: If required environment variables are missing.
    """
    evm_private_key = os.getenv("EVM_PRIVATE_KEY")
    svm_private_key = os.getenv("SVM_PRIVATE_KEY")
    avm_mnemonic = os.getenv("AVM_MNEMONIC")
    base_url = os.getenv("RESOURCE_SERVER_URL", "http://localhost:4021")
    endpoint_path = os.getenv("ENDPOINT_PATH", "/weather")

    if not evm_private_key and not svm_private_key and not avm_mnemonic:
        print("Error: At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_MNEMONIC required")
        print("Please copy .env-local to .env and fill in the values.")
        sys.exit(1)

    return evm_private_key, svm_private_key, avm_mnemonic, f"{base_url}{endpoint_path}"


async def run_hooks_example(
    evm_private_key: str | None,
    svm_private_key: str | None,
    avm_mnemonic: str | None,
    url: str,
) -> None:
    """Run the hooks example."""
    from hooks import run_hooks_example

    await run_hooks_example(evm_private_key, svm_private_key, avm_mnemonic, url)


async def run_preferred_network_example(
    evm_private_key: str | None,
    svm_private_key: str | None,
    avm_mnemonic: str | None,
    url: str,
) -> None:
    """Run the preferred network example."""
    from preferred_network import run_preferred_network_example

    await run_preferred_network_example(evm_private_key, svm_private_key, avm_mnemonic, url)


async def run_builder_pattern_example(
    evm_private_key: str | None,
    svm_private_key: str | None,
    avm_mnemonic: str | None,
    url: str,
) -> None:
    """Run the builder pattern example."""
    from builder_pattern import run_builder_pattern_example

    await run_builder_pattern_example(evm_private_key, svm_private_key, avm_mnemonic, url)


EXAMPLE_RUNNERS = {
    "hooks": run_hooks_example,
    "preferred_network": run_preferred_network_example,
    "builder_pattern": run_builder_pattern_example,
}


async def run_example(
    name: str,
    evm_private_key: str | None,
    svm_private_key: str | None,
    avm_mnemonic: str | None,
    url: str,
) -> None:
    """Run a specific example.

    Args:
        name: Name of the example to run.
        evm_private_key: EVM private key for signing.
        svm_private_key: SVM private key for signing.
        avm_mnemonic: AVM mnemonic for signing.
        url: URL to make the request to.
    """
    print(f"\n{'=' * 60}")
    print(f"Running: {name}")
    print(f"Description: {EXAMPLES[name]}")
    print(f"{'=' * 60}\n")

    runner = EXAMPLE_RUNNERS[name]
    await runner(evm_private_key, svm_private_key, avm_mnemonic, url)


async def run_all_examples(
    evm_private_key: str | None,
    svm_private_key: str | None,
    avm_mnemonic: str | None,
    url: str,
) -> None:
    """Run all examples sequentially.

    Args:
        evm_private_key: EVM private key for signing.
        svm_private_key: SVM private key for signing.
        avm_mnemonic: AVM mnemonic for signing.
        url: URL to make the request to.
    """
    for name in EXAMPLES:
        try:
            await run_example(name, evm_private_key, svm_private_key, avm_mnemonic, url)
        except Exception as e:
            print(f"\n❌ Example '{name}' failed: {e}")
        print()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Advanced x402 client examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available examples:
  hooks              Payment lifecycle hooks (before, after, failure)
  preferred_network  Custom network preference selector
  builder_pattern    Network-specific registration with builder pattern
  all                Run all examples sequentially
""",
    )
    parser.add_argument(
        "example",
        nargs="?",
        default="hooks",
        choices=[*EXAMPLES.keys(), "all"],
        help="Example to run (default: hooks)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available examples",
    )

    args = parser.parse_args()

    if args.list:
        print("Available examples:\n")
        for name, desc in EXAMPLES.items():
            print(f"  {name:20} {desc}")
        print(f"\n  {'all':20} Run all examples sequentially")
        return

    evm_private_key, svm_private_key, avm_mnemonic, url = validate_environment()

    if args.example == "all":
        asyncio.run(run_all_examples(evm_private_key, svm_private_key, avm_mnemonic, url))
    else:
        asyncio.run(run_example(args.example, evm_private_key, svm_private_key, avm_mnemonic, url))


if __name__ == "__main__":
    main()
