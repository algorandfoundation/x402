"""Exact payment scheme for AVM (Algorand).

Provides client, server, and facilitator implementations
for the exact payment scheme on Algorand networks.

Usage:
    ```python
    from x402.mechanisms.avm.exact import (
        ExactAvmScheme,
        register_exact_avm_client,
        register_exact_avm_facilitator,
    )

    # Client-side
    from x402.mechanisms.avm import AlgorandSigner
    signer = AlgorandSigner.from_mnemonic("word1 word2 ... word25")
    client = x402Client()
    register_exact_avm_client(client, signer)

    # Facilitator-side
    from x402.mechanisms.avm import FacilitatorAlgorandSigner
    fac_signer = FacilitatorAlgorandSigner()
    fac_signer.add_account(private_key)
    facilitator = x402Facilitator()
    register_exact_avm_facilitator(facilitator, fac_signer, networks)
    ```
"""

# Client scheme
from .client import ExactAvmScheme as ExactAvmClientScheme

# Server scheme
from .server import ExactAvmScheme as ExactAvmServerScheme

# Facilitator scheme
from .facilitator import ExactAvmScheme as ExactAvmFacilitatorScheme

# Registration helpers
from .register import (
    register_exact_avm_client,
    register_exact_avm_facilitator,
    register_exact_avm_server,
)

# V1 compatibility
from . import v1

# For convenience, export the main scheme class
# (use the appropriate import for client/server/facilitator)
ExactAvmScheme = ExactAvmClientScheme

__all__ = [
    # Schemes
    "ExactAvmScheme",
    "ExactAvmClientScheme",
    "ExactAvmServerScheme",
    "ExactAvmFacilitatorScheme",
    # Registration helpers
    "register_exact_avm_client",
    "register_exact_avm_server",
    "register_exact_avm_facilitator",
    # V1 compatibility
    "v1",
]
