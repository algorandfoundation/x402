import { config } from "dotenv";
import { x402Client, wrapFetchWithPayment, x402HTTPClient } from "@x402/fetch";
import { registerExactEvmScheme } from "@x402/evm/exact/client";
import { registerExactSvmScheme } from "@x402/svm/exact/client";
import { registerExactAvmScheme } from "@x402/avm/exact/client";
import { privateKeyToAccount } from "viem/accounts";
import { createKeyPairSignerFromBytes } from "@solana/kit";
import { base58 } from "@scure/base";
import algosdk from "algosdk";

config();

const evmPrivateKey = process.env.EVM_PRIVATE_KEY as `0x${string}`;
const svmPrivateKey = process.env.SVM_PRIVATE_KEY as string;
const avmPrivateKey = process.env.AVM_PRIVATE_KEY as string;
const baseURL = process.env.RESOURCE_SERVER_URL || "http://localhost:4021";
const endpointPath = process.env.ENDPOINT_PATH || "/weather";
const url = `${baseURL}${endpointPath}`;

/**
 * Example demonstrating how to use @x402/fetch to make requests to x402-protected endpoints.
 *
 * This uses the helper registration functions from @x402/evm and @x402/svm to register
 * all supported networks for both v1 and v2 protocols.
 *
 * Required environment variables:
 * - EVM_PRIVATE_KEY: The private key of the EVM signer
 * - SVM_PRIVATE_KEY: The private key of the SVM signer
 * - AVM_PRIVATE_KEY: The private key of the AVM signer (Base64-encoded 64-byte key)
 */
async function main(): Promise<void> {
  const evmSigner = privateKeyToAccount(evmPrivateKey);
  const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));

  const secretKey = Buffer.from(avmPrivateKey, "base64");
  if (secretKey.length !== 64) {
    throw new Error("AVM_PRIVATE_KEY must be a Base64-encoded 64-byte key");
  }
  const address = algosdk.encodeAddress(secretKey.slice(32));
  const avmSigner = {
    address,
    signTransactions: async (txns: Uint8Array[], indexesToSign?: number[]) => {
      return txns.map((txn, i) => {
        if (indexesToSign && !indexesToSign.includes(i)) return null;
        const decoded = algosdk.decodeUnsignedTransaction(txn);
        const signed = algosdk.signTransaction(decoded, secretKey);
        return signed.blob;
      });
    },
  };

  const client = new x402Client();
  registerExactEvmScheme(client, { signer: evmSigner });
  registerExactSvmScheme(client, { signer: svmSigner });
  registerExactAvmScheme(client, { signer: avmSigner });
  console.info(`AVM signer: ${address}`);

  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  console.log(`Making request to: ${url}\n`);
  const response = await fetchWithPayment(url, { method: "GET" });
  const body = await response.json();
  console.log("Response body:", body);

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
