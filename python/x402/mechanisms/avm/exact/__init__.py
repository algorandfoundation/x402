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

    # Client-side: implement ClientAvmSigner protocol with algosdk
    import base64, algosdk
    secret_key = base64.b64decode(os.environ["AVM_PRIVATE_KEY"])
    address = algosdk.encoding.encode_address(secret_key[32:])
    # ... implement sign_transactions method (see examples)
    client = x402Client()
    register_exact_avm_client(client, signer)

    # Facilitator-side: implement FacilitatorAvmSigner protocol with algosdk
    # ... implement get_addresses, sign_transaction, simulate_group, etc. (see examples)
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
