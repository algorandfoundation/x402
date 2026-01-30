# @x402/avm

AVM (Algorand Virtual Machine) implementation of the x402 payment protocol using the **Exact** payment scheme with ASA (Algorand Standard Asset) transfers.

## Installation

```bash
npm install @x402/avm
```

## Overview

This package provides three main components for handling x402 payments on Algorand:

- **Client** - For applications that need to make payments (have wallets/signers)
- **Facilitator** - For payment processors that verify and execute on-chain transactions
- **Service** - For resource servers that accept payments and build payment requirements

## Package Exports

### Main Package (`@x402/avm`)

**V2 Protocol Support** - Modern x402 protocol with CAIP-2 network identifiers

**Client:**
- `ExactAvmClient` - V2 client implementation using ASA transfers
- `toClientAvmSigner(account)` - Converts Algorand accounts to x402 signers
- `ClientAvmSigner` - TypeScript type for client signers

**Facilitator:**
- `ExactAvmFacilitator` - V2 facilitator for payment verification and settlement
- `toFacilitatorAvmSigner(account)` - Converts Algorand accounts to facilitator signers
- `FacilitatorAvmSigner` - TypeScript type for facilitator signers

**Service:**
- `ExactAvmServer` - V2 service for building payment requirements

### V1 Package (`@x402/avm/v1`)

**V1 Protocol Support** - Legacy x402 protocol with simple network names

**Exports:**
- `ExactAvmClientV1` - V1 client implementation
- `ExactAvmFacilitatorV1` - V1 facilitator implementation
- `NETWORKS` - Array of all supported V1 network names

**Supported V1 Networks:**
```typescript
[
  "algorand-mainnet",  // Mainnet
  "algorand-testnet"   // Testnet
]
```

## Version Differences

### V2 (Main Package)
- Network format: CAIP-2 (`algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73k`)
- Wildcard support: Yes (`algorand:*`)
- Payload structure: Partial (core wraps with metadata)
- Extensions: Full support
- Transaction: Atomic group with optional fee payer

### V1 (V1 Package)
- Network format: Simple names (`algorand-testnet`)
- Wildcard support: No (fixed list)
- Payload structure: Complete
- Extensions: Limited
- Transaction: Atomic group with optional fee payer

## Usage Patterns

### 1. Direct Registration

```typescript
import { x402Client } from "@x402/core/client";
import { ExactAvmClient } from "@x402/avm";
import { ExactAvmClientV1 } from "@x402/avm/v1";

const client = new x402Client()
  .register("algorand:*", new ExactAvmClient(signer))
  .registerSchemeV1("algorand-testnet", new ExactAvmClientV1(signer))
  .registerSchemeV1("algorand-mainnet", new ExactAvmClientV1(signer));
```

### 2. Using Config (Flexible)

```typescript
import { x402Client } from "@x402/core/client";
import { ExactAvmClient } from "@x402/avm";

const client = x402Client.fromConfig({
  schemes: [
    { network: "algorand:*", client: new ExactAvmClient(signer) },
    {
      network: "algorand-testnet",
      client: new ExactAvmClientV1(signer),
      x402Version: 1
    }
  ]
});
```

## Supported Networks

**V2 Networks** (via CAIP-2):
- `algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73k` - Mainnet
- `algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDe` - Testnet
- `algorand:*` - Wildcard (matches all Algorand networks)

**V1 Networks** (simple names):
- `algorand-mainnet` - Mainnet
- `algorand-testnet` - Testnet

## Asset Support

Supports Algorand Standard Assets (ASA):
- USDC (primary)
- Any ASA with proper opt-in

## Transaction Structure

The exact payment scheme uses atomic transaction groups with:
- Payment transaction (ASA transfer or ALGO payment)
- Optional fee payer transaction (gasless transactions)
- Transaction simulation for validation

## Development

```bash
# Build
pnpm build

# Test
pnpm test

# Integration tests
pnpm test:integration

# Lint & Format
pnpm lint
pnpm format
```

## Related Packages

- `@x402/core` - Core protocol types and client
- `@x402/fetch` - HTTP wrapper with automatic payment handling
- `@x402/evm` - EVM/Ethereum implementation
- `@x402/svm` - Solana/SVM implementation
- `algosdk` - Algorand JavaScript SDK (peer dependency)
