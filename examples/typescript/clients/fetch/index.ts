import { config } from "dotenv";
import { x402Client, wrapFetchWithPayment, x402HTTPClient } from "@x402/fetch";

config();

const evmPrivateKey = process.env.EVM_PRIVATE_KEY as `0x${string}`;
const svmPrivateKey = process.env.SVM_PRIVATE_KEY as string;
const avmMnemonic = process.env.AVM_MNEMONIC as string;
const baseURL = process.env.RESOURCE_SERVER_URL || "http://localhost:4021";
const endpointPath = process.env.ENDPOINT_PATH || "/weather";
const url = `${baseURL}${endpointPath}`;

// Validate at least one credential is configured
if (!evmPrivateKey && !svmPrivateKey && !avmMnemonic) {
  console.error("❌ At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_MNEMONIC must be set");
  process.exit(1);
}

/**
 * Example demonstrating how to use @x402/fetch to make requests to x402-protected endpoints.
 *
 * This uses the helper registration functions from @x402/evm, @x402/svm, and @x402/avm to register
 * networks conditionally based on which credentials are provided.
 *
 * Environment variables (at least one required):
 * - EVM_PRIVATE_KEY: The private key of the EVM signer
 * - SVM_PRIVATE_KEY: The private key of the SVM signer
 * - AVM_MNEMONIC: The 25-word mnemonic phrase for the Algorand signer
 */
async function main(): Promise<void> {
  const client = new x402Client();
  const enabledNetworks: string[] = [];

  // Conditionally register EVM support
  if (evmPrivateKey) {
    const { registerExactEvmScheme } = await import("@x402/evm/exact/client");
    const { privateKeyToAccount } = await import("viem/accounts");

    const evmSigner = privateKeyToAccount(evmPrivateKey);
    registerExactEvmScheme(client, { signer: evmSigner });
    enabledNetworks.push("EVM");
    console.info(`EVM signer: ${evmSigner.address}`);
  }

  // Conditionally register SVM support
  if (svmPrivateKey) {
    const { registerExactSvmScheme } = await import("@x402/svm/exact/client");
    const { createKeyPairSignerFromBytes } = await import("@solana/kit");
    const { base58 } = await import("@scure/base");

    const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
    registerExactSvmScheme(client, { signer: svmSigner });
    enabledNetworks.push("SVM");
    console.info(`SVM signer: ${svmSigner.address}`);
  }

  // Conditionally register AVM (Algorand) support
  if (avmMnemonic) {
    const { registerExactAvmScheme } = await import("@x402/avm/exact/client");
    const { toClientAvmSigner } = await import("@x402/avm");
    const algosdk = await import("algosdk");

    const avmAccount = algosdk.default.mnemonicToSecretKey(avmMnemonic);
    const avmSigner = toClientAvmSigner(avmAccount);
    registerExactAvmScheme(client, { signer: avmSigner });
    enabledNetworks.push("AVM");
    console.info(`AVM signer: ${avmAccount.addr.toString()}`);
  }

  console.info(`Enabled networks: ${enabledNetworks.join(", ")}\n`);

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
