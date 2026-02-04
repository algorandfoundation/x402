# Custom x402 Client Implementation

Demonstrates how to implement x402 payment handling manually using only the core packages, without convenience wrappers like `@x402/fetch` or `@x402/axios`. Supports EVM (Ethereum), SVM (Solana), and AVM (Algorand) networks.

```typescript
import { x402Client } from "@x402/core/client";
import { decodePaymentRequiredHeader, encodePaymentSignatureHeader } from "@x402/core/http";
import { ExactEvmScheme } from "@x402/evm/exact/client";
import { ExactAvmScheme } from "@x402/avm/exact/client";
import { privateKeyToAccount } from "viem/accounts";
import { toClientAvmSigner, mnemonicToAlgorandAccount } from "@x402/avm";

const client = new x402Client()
  .register("eip155:*", new ExactEvmScheme(privateKeyToAccount(evmPrivateKey)))
  .register("algorand:*", new ExactAvmScheme(toClientAvmSigner(mnemonicToAlgorandAccount(avmMnemonic))));

// 1. Make initial request
let response = await fetch(url);

// 2. Handle 402 Payment Required
if (response.status === 402) {
  const paymentRequired = decodePaymentRequiredHeader(response.headers.get("PAYMENT-REQUIRED"));
  const paymentPayload = await client.createPaymentPayload(paymentRequired);

  // 3. Retry with payment
  response = await fetch(url, {
    headers: { "PAYMENT-SIGNATURE": encodePaymentSignatureHeader(paymentPayload) },
  });
}

console.log(await response.json());
```

## Prerequisites

- Node.js v20+ (install via [nvm](https://github.com/nvm-sh/nvm))
- pnpm v10 (install via [pnpm.io/installation](https://pnpm.io/installation))
- Valid credentials for at least one network:
  - EVM: Private key (hex string starting with 0x)
  - SVM: Private key (base58 encoded)
  - AVM: Algorand mnemonic phrase (supports both 24-word BIP-39 and 25-word Algorand native mnemonics)
- A running x402 server (see [server examples](../../servers/))

## Setup

1. Copy `.env-local` to `.env`:

```bash
cp .env-local .env
```

and configure at least one of the following environment variables:

- `EVM_PRIVATE_KEY` - Ethereum private key for EVM payments (optional)
- `SVM_PRIVATE_KEY` - Solana private key for SVM payments (optional)
- `AVM_MNEMONIC` - Algorand mnemonic for AVM payments (supports both 24-word BIP-39 and 25-word native) (optional)

Only networks with configured credentials will be registered.

2. Install and build all packages from the typescript examples root:

```bash
cd ../../
pnpm install && pnpm build
cd clients/custom
```

3. Run the example

```bash
pnpm dev
```

## Testing the Example

Start a server first:

```bash
cd ../../servers/express
pnpm dev
```

Then run the custom client:

```bash
cd ../../clients/custom
pnpm dev
```

## HTTP Headers (v2 Protocol)

| Header              | Direction       | Description                            |
| ------------------- | --------------- | -------------------------------------- |
| `PAYMENT-REQUIRED`  | Server → Client | 402 response with payment requirements |
| `PAYMENT-SIGNATURE` | Client → Server | Retry request with payment payload     |
| `PAYMENT-RESPONSE`  | Server → Client | 200 response with settlement details   |

## Payment Flow

1. **Initial Request** — Make HTTP request to protected endpoint
2. **402 Response** — Server responds with requirements in `PAYMENT-REQUIRED` header
3. **Parse Requirements** — Decode requirements using `decodePaymentRequiredHeader()`
4. **Create Payment** — Use `x402Client.createPaymentPayload()` to generate payload
5. **Encode Payment** — Use `encodePaymentSignatureHeader()` for the header value
6. **Retry with Payment** — Make new request with `PAYMENT-SIGNATURE` header
7. **Success** — Receive 200 with settlement in `PAYMENT-RESPONSE` header

## Key Implementation Details

### 1. Setting Up the Client with Multi-Network Support

```typescript
import { x402Client } from "@x402/core/client";

const client = new x402Client();

// Conditionally add EVM support
if (evmPrivateKey) {
  const { ExactEvmScheme } = await import("@x402/evm/exact/client");
  const { privateKeyToAccount } = await import("viem/accounts");
  client.register("eip155:*", new ExactEvmScheme(privateKeyToAccount(evmPrivateKey)));
}

// Conditionally add SVM support
if (svmPrivateKey) {
  const { ExactSvmScheme } = await import("@x402/svm/exact/client");
  const { createKeyPairSignerFromBytes } = await import("@solana/kit");
  const { base58 } = await import("@scure/base");
  const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
  client.register("solana:*", new ExactSvmScheme(svmSigner));
}

// Conditionally add AVM (Algorand) support
if (avmMnemonic) {
  const { ExactAvmScheme } = await import("@x402/avm/exact/client");
  const { toClientAvmSigner, mnemonicToAlgorandAccount } = await import("@x402/avm");
  const avmSigner = toClientAvmSigner(mnemonicToAlgorandAccount(avmMnemonic));
  client.register("algorand:*", new ExactAvmScheme(avmSigner));
}
```

### 2. Detecting Payment Required

```typescript
import { decodePaymentRequiredHeader } from "@x402/core/http";

if (response.status === 402) {
  const paymentRequiredHeader = response.headers.get("PAYMENT-REQUIRED");
  const paymentRequired = decodePaymentRequiredHeader(paymentRequiredHeader);
  // paymentRequired.accepts contains the payment options
}
```

### 3. Creating Payment Payload

```typescript
import { encodePaymentSignatureHeader } from "@x402/core/http";

const paymentPayload = await client.createPaymentPayload(paymentRequired);
const paymentHeader = encodePaymentSignatureHeader(paymentPayload);
```

### 4. Retrying with Payment

```typescript
const response = await fetch(url, {
  headers: {
    "PAYMENT-SIGNATURE": paymentHeader,
  },
});
```

### 5. Extracting Settlement

```typescript
import { decodePaymentResponseHeader } from "@x402/core/http";

const settlementHeader = response.headers.get("PAYMENT-RESPONSE");
const settlement = decodePaymentResponseHeader(settlementHeader);
// settlement.transaction, settlement.network, settlement.payer
```

## Wrapper vs Custom Comparison

| Aspect            | With Wrapper (@x402/fetch) | Custom Implementation |
| ----------------- | -------------------------- | --------------------- |
| Code Complexity   | ~10 lines                  | ~100 lines            |
| Automatic Retry   | Yes                        | Manual                |
| Error Handling    | Built-in                   | You implement         |
| Header Management | Automatic                  | Manual                |
| Flexibility       | Limited                    | Complete control      |

## When to Use Custom Implementation

- Need complete control over every step of the payment flow
- Integrating with non-standard HTTP libraries
- Implementing custom retry/error logic
- Learning how x402 works under the hood

## Adapting to Other HTTP Clients

To use this pattern with other HTTP clients (axios, got, etc.):

1. Detect 402 status code
2. Extract requirements from `PAYMENT-REQUIRED` header
3. Use `decodePaymentRequiredHeader()` to parse
4. Use `x402Client.createPaymentPayload()` to create payload
5. Use `encodePaymentSignatureHeader()` to encode
6. Add `PAYMENT-SIGNATURE` header to retry request
7. Extract settlement from `PAYMENT-RESPONSE` header
