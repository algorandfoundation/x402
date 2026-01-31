"""V1 backward compatibility wrappers for AVM exact payment scheme.

These wrappers provide backward compatibility for V1 protocol clients
by mapping V1 network names to V2 CAIP-2 identifiers.

Note: This does NOT add code to the deprecated python/legacy/ directory.
These are V1-compatible wrappers within the V2 SDK architecture.
"""

from .client import ExactAvmSchemeV1 as ExactAvmSchemeV1Client
from .facilitator import ExactAvmSchemeV1 as ExactAvmSchemeV1Facilitator

# For convenience, expose both
ExactAvmSchemeV1 = ExactAvmSchemeV1Client

__all__ = [
    "ExactAvmSchemeV1",
    "ExactAvmSchemeV1Client",
    "ExactAvmSchemeV1Facilitator",
]
