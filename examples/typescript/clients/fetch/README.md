# @x402/fetch Example Client

Example client demonstrating how to use `@x402/fetch` to make HTTP requests to endpoints protected by the x402 payment protocol. Supports EVM (Ethereum), SVM (Solana), and AVM (Algorand) networks.

```typescript
import { x402Client, wrapFetchWithPayment } from "@x402/fetch";
import { registerExactEvmScheme } from "@x402/evm/exact/client";
import { registerExactSvmScheme } from "@x402/svm/exact/client";
import { registerExactAvmScheme } from "@x402/avm/exact/client";
import { privateKeyToAccount } from "viem/accounts";
import { createKeyPairSignerFromBytes } from "@solana/kit";
import algosdk from "algosdk";
import { base58 } from "@scure/base";

const client = new x402Client();
registerExactEvmScheme(client, { signer: privateKeyToAccount(process.env.EVM_PRIVATE_KEY) });
registerExactSvmScheme(client, { signer: await createKeyPairSignerFromBytes(base58.decode(process.env.SVM_PRIVATE_KEY)) });

// Create AVM signer from Base64 private key
const secretKey = Buffer.from(process.env.AVM_PRIVATE_KEY!, "base64");
const avmSigner = {
  address: algosdk.encodeAddress(secretKey.slice(32)),
  signTransactions: async (txns: Uint8Array[], indexesToSign?: number[]) => {
    return txns.map((txn, i) => {
      if (indexesToSign && !indexesToSign.includes(i)) return null;
      const decoded = algosdk.decodeUnsignedTransaction(txn);
      const signed = algosdk.signTransaction(decoded, secretKey);
      return signed.blob;
    });
  },
};
registerExactAvmScheme(client, { signer: avmSigner });

const fetchWithPayment = wrapFetchWithPayment(fetch, client);

const response = await fetchWithPayment("http://localhost:4021/weather");
console.log(await response.json());
```

## Prerequisites

- Node.js v20+ (install via [nvm](https://github.com/nvm-sh/nvm))
- pnpm v10 (install via [pnpm.io/installation](https://pnpm.io/installation))
- A running x402 server (see [express server example](../../servers/express))
- Valid EVM and/or SVM private keys, and/or AVM private key for making payments

## Setup

1. Install and build all packages from the typescript examples root:

```bash
cd ../../
pnpm install && pnpm build
cd clients/fetch
```

2. Copy `.env-local` to `.env` and add your private keys:

```bash
cp .env-local .env
```

Configure at least one of the following environment variables:

- `EVM_PRIVATE_KEY` - Ethereum private key for EVM payments (optional)
- `SVM_PRIVATE_KEY` - Solana private key for SVM payments (optional)
- `AVM_PRIVATE_KEY` - Base64-encoded 64-byte Algorand private key for AVM payments (optional)

Only networks with configured credentials will be registered.

3. Run the client:

```bash
pnpm start
```

## Next Steps

See [Advanced Examples](../advanced/) for builder pattern registration, payment lifecycle hooks, and network preferences.
