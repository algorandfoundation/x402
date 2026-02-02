import { config } from "dotenv";
import { x402Client } from "@x402/core/client";
import {
  decodePaymentRequiredHeader,
  decodePaymentResponseHeader,
  encodePaymentSignatureHeader,
} from "@x402/core/http";
import type { PaymentRequirements } from "@x402/core/types";

config();

/**
 * Custom x402 Client Implementation (v2 Protocol)
 *
 * This example demonstrates how to implement x402 payment handling manually
 * using only the core packages, without the convenience wrappers like @x402/fetch.
 *
 * x402 v2 Protocol Headers:
 * - PAYMENT-REQUIRED: Server → Client (402 response)
 * - PAYMENT-SIGNATURE: Client → Server (retry with payment)
 * - PAYMENT-RESPONSE: Server → Client (settlement confirmation)
 */

const evmPrivateKey = process.env.EVM_PRIVATE_KEY as `0x${string}`;
const svmPrivateKey = process.env.SVM_PRIVATE_KEY as string;
const avmMnemonic = process.env.AVM_MNEMONIC as string;
const baseURL = process.env.SERVER_URL || "http://localhost:4021";
const url = `${baseURL}/weather`;

/**
 * Makes a request with x402 payment handling.
 *
 * @param client - The x402 client instance to use for payments
 * @param url - The URL to request
 */
async function makeRequestWithPayment(client: x402Client, url: string): Promise<void> {
  console.log(`\n🌐 Making initial request to: ${url}\n`);

  // Step 1: Make initial request
  let response = await fetch(url);
  console.log(`📥 Initial response status: ${response.status}\n`);

  // Step 2: Handle 402 Payment Required
  if (response.status === 402) {
    console.log("💳 Payment required! Processing...\n");

    // Decode payment requirements from PAYMENT-REQUIRED header
    const paymentRequiredHeader = response.headers.get("PAYMENT-REQUIRED");
    if (!paymentRequiredHeader) {
      throw new Error("Missing PAYMENT-REQUIRED header");
    }
    const paymentRequired = decodePaymentRequiredHeader(paymentRequiredHeader);

    const requirements: PaymentRequirements[] = Array.isArray(paymentRequired.accepts)
      ? paymentRequired.accepts
      : [paymentRequired.accepts];

    console.log("📋 Payment requirements:");
    requirements.forEach((req, i) => {
      console.log(`   ${i + 1}. ${req.network} / ${req.scheme} - ${req.amount}`);
    });

    // Step 3: Create and encode payment
    console.log("\n🔐 Creating payment...\n");
    const paymentPayload = await client.createPaymentPayload(paymentRequired);
    const paymentHeader = encodePaymentSignatureHeader(paymentPayload);

    // Step 4: Retry with PAYMENT-SIGNATURE header
    console.log("🔄 Retrying with payment...\n");
    response = await fetch(url, {
      headers: { "PAYMENT-SIGNATURE": paymentHeader },
    });
    console.log(`📥 Response status: ${response.status}\n`);
  }

  // Step 5: Handle success
  if (response.status === 200) {
    console.log("✅ Success!\n");
    console.log("Response:", await response.json());

    // Decode settlement from PAYMENT-RESPONSE header
    const settlementHeader = response.headers.get("PAYMENT-RESPONSE");
    if (settlementHeader) {
      const settlement = decodePaymentResponseHeader(settlementHeader);
      console.log("\n💰 Settlement:");
      console.log(`   Transaction: ${settlement.transaction}`);
      console.log(`   Network: ${settlement.network}`);
      console.log(`   Payer: ${settlement.payer}`);
    }
  } else {
    throw new Error(`Unexpected status: ${response.status}`);
  }
}

/**
 * Main entry point demonstrating custom x402 client usage.
 */
async function main(): Promise<void> {
  console.log("\n🔧 Custom x402 Client (v2 Protocol)\n");

  // Validate at least one network is configured
  if (!evmPrivateKey && !svmPrivateKey && !avmMnemonic) {
    console.error("❌ At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_MNEMONIC must be set");
    process.exit(1);
  }

  const client = new x402Client();
  const enabledNetworks: string[] = [];

  // Conditionally add EVM support
  if (evmPrivateKey) {
    const { privateKeyToAccount } = await import("viem/accounts");
    const { ExactEvmScheme } = await import("@x402/evm/exact/client");

    const evmSigner = privateKeyToAccount(evmPrivateKey);
    client.register("eip155:*", new ExactEvmScheme(evmSigner));
    enabledNetworks.push("EVM (eip155:*)");
  }

  // Conditionally add SVM support
  if (svmPrivateKey) {
    const { ExactSvmScheme } = await import("@x402/svm/exact/client");
    const { createKeyPairSignerFromBytes } = await import("@solana/kit");
    const { base58 } = await import("@scure/base");

    const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
    client.register("solana:*", new ExactSvmScheme(svmSigner));
    enabledNetworks.push("SVM (solana:*)");
  }

  // Conditionally add AVM (Algorand) support
  if (avmMnemonic) {
    const algosdk = await import("algosdk");
    const { ExactAvmScheme } = await import("@x402/avm/exact/client");
    const { toClientAvmSigner } = await import("@x402/avm");

    const avmAccount = algosdk.default.mnemonicToSecretKey(avmMnemonic);
    const avmSigner = toClientAvmSigner(avmAccount);
    client.register("algorand:*", new ExactAvmScheme(avmSigner));
    enabledNetworks.push("AVM (algorand:*)");
  }

  console.log(`Enabled networks: ${enabledNetworks.join(", ")}`);
  console.log("✅ Client ready\n");

  await makeRequestWithPayment(client, url);
  console.log("\n🎉 Done!");
}

main().catch(error => {
  console.error("\n❌ Error:", error.message);
  process.exit(1);
});
