/**
 * All Networks Client Example
 *
 * Demonstrates how to create a client that supports all available networks with
 * optional chain configuration via environment variables.
 *
 * New chain support should be added here in alphabetic order by network prefix
 * (e.g., "algorand" before "eip155" before "solana").
 */

import { config } from "dotenv";
import { x402Client, wrapFetchWithPayment, x402HTTPClient } from "@x402/fetch";
import { ExactAvmScheme } from "@x402/avm/exact/client";
import { ExactEvmScheme } from "@x402/evm/exact/client";
import { ExactSvmScheme } from "@x402/svm/exact/client";
import { encodeAddress } from "@algorandfoundation/algokit-utils/common";
import { ed25519Generator } from "@algorandfoundation/algokit-utils/crypto";
import {
  decodeTransaction,
  bytesForSigning,
  encodeSignedTransaction,
} from "@algorandfoundation/algokit-utils/transact";
import { base58 } from "@scure/base";
import { createKeyPairSignerFromBytes } from "@solana/kit";
import { privateKeyToAccount } from "viem/accounts";

config();

// Configuration - optional per network
const avmPrivateKey = process.env.AVM_PRIVATE_KEY as string | undefined;
const evmPrivateKey = process.env.EVM_PRIVATE_KEY as `0x${string}` | undefined;
const svmPrivateKey = process.env.SVM_PRIVATE_KEY as string | undefined;
const baseURL = process.env.RESOURCE_SERVER_URL || "http://localhost:4021";
const endpointPath = process.env.ENDPOINT_PATH || "/weather";
const url = `${baseURL}${endpointPath}`;

/**
 * Example demonstrating how to use @x402/fetch with all supported networks.
 * Schemes are registered directly for networks where private keys are provided.
 */
async function main(): Promise<void> {
  // Validate at least one private key is provided
  if (!avmPrivateKey && !evmPrivateKey && !svmPrivateKey) {
    console.error("❌ At least one of AVM_PRIVATE_KEY, EVM_PRIVATE_KEY, or SVM_PRIVATE_KEY is required");
    process.exit(1);
  }

  // Create x402 client
  const client = new x402Client();

  // Register AVM scheme if private key is provided
  if (avmPrivateKey) {
    const avmSecretKey = Buffer.from(avmPrivateKey, "base64");
    const avmSeed = avmSecretKey.slice(0, 32);
    const { ed25519Pubkey, rawEd25519Signer } = ed25519Generator(avmSeed);
    const avmAddress = encodeAddress(ed25519Pubkey);
    const avmSigner = {
      address: avmAddress,
      signTransactions: async (txns: Uint8Array[], indexesToSign?: number[]) => {
        return Promise.all(
          txns.map(async (txn, i) => {
            if (indexesToSign && !indexesToSign.includes(i)) return null;
            const decoded = decodeTransaction(txn);
            const msg = bytesForSigning.transaction(decoded);
            const sig = await rawEd25519Signer(msg);
            return encodeSignedTransaction({ txn: decoded, sig });
          }),
        );
      },
    };
    client.register("algorand:*", new ExactAvmScheme(avmSigner));
    console.log(`Initialized AVM account: ${avmAddress}`);
  }

  // Register EVM scheme if private key is provided
  if (evmPrivateKey) {
    const evmSigner = privateKeyToAccount(evmPrivateKey);
    client.register("eip155:*", new ExactEvmScheme(evmSigner));
    console.log(`Initialized EVM account: ${evmSigner.address}`);
  }

  // Register SVM scheme if private key is provided
  if (svmPrivateKey) {
    const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
    client.register("solana:*", new ExactSvmScheme(svmSigner));
    console.log(`Initialized SVM account: ${svmSigner.address}`);
  }

  // Wrap fetch with payment handling
  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  console.log(`\nMaking request to: ${url}\n`);

  // Make the request
  const response = await fetchWithPayment(url, { method: "GET" });
  const body = await response.json();
  console.log("Response body:", body);

  // Extract payment response if present
  if (response.ok) {
    const paymentResponse = new x402HTTPClient(client).getPaymentSettleResponse(name =>
      response.headers.get(name),
    );
    console.log("\nPayment response:", JSON.stringify(paymentResponse, null, 2));
  } else {
    console.log(`\nNo payment settled (response status: ${response.status})`);
  }
}

main().catch(error => {
  console.error(error?.response?.data?.error ?? error);
  process.exit(1);
});
