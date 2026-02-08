import { privateKeyToAccount } from "viem/accounts";
import { x402Client, wrapFetchWithPayment, x402HTTPClient } from "@x402/fetch";
import { ExactEvmScheme } from "@x402/evm/exact/client";
import { ExactSvmScheme } from "@x402/svm/exact/client";
import { ExactAvmScheme } from "@x402/avm/exact/client";
import { ALGORAND_TESTNET_CAIP2 } from "@x402/avm";
import algosdk from "algosdk";
import { createKeyPairSignerFromBytes } from "@solana/kit";
import { base58 } from "@scure/base";

/**
 * Builder Pattern Example
 *
 * This demonstrates how to configure the x402Client using the builder pattern,
 * chaining .register() calls to map network patterns to mechanism schemes.
 *
 * Use this approach when you need:
 * - Different signers for different networks (e.g., separate keys for mainnet vs testnet)
 * - Fine-grained control over which networks are supported
 * - Custom scheme configurations per network
 *
 * @param evmPrivateKey - The EVM private key for signing
 * @param svmPrivateKey - The SVM private key for signing
 * @param url - The URL to make the request to
 */
export async function runBuilderPatternExample(
  evmPrivateKey: `0x${string}`,
  svmPrivateKey: string,
  avmPrivateKey: string,
  url: string,
): Promise<void> {
  console.log("🔧 Creating client with builder pattern...\n");

  const evmSigner = privateKeyToAccount(evmPrivateKey);
  const ethereumMainnetSigner = evmSigner; // Could be a different signer for mainnet
  const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
  const solanaDevnetSigner = svmSigner; // Could be a different signer for devnet

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
  const algorandTestnetSigner = avmSigner; // Could be a different signer for testnet

  // Builder pattern allows fine-grained control over network registration
  // More specific patterns (e.g., "eip155:1") take precedence over wildcards (e.g., "eip155:*")
  const client = new x402Client()
    .register("eip155:*", new ExactEvmScheme(evmSigner)) // All EVM networks
    .register("eip155:1", new ExactEvmScheme(ethereumMainnetSigner)) // Ethereum mainnet override
    .register("solana:*", new ExactSvmScheme(svmSigner)) // All Solana networks
    .register("solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", new ExactSvmScheme(solanaDevnetSigner)) // Devnet override
    .register("algorand:*", new ExactAvmScheme(avmSigner)) // All Algorand networks
    .register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme(algorandTestnetSigner)); // Testnet override

  console.log("Registered networks:");
  console.log("  - eip155:* (all EVM) with default signer");
  console.log("  - eip155:1 (Ethereum mainnet) with mainnet signer");
  console.log("  - solana:* (all Solana) with default signer");
  console.log("  - solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1 (devnet) with devnet signer");
  console.log();

  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  console.log(`🌐 Making request to: ${url}\n`);
  const response = await fetchWithPayment(url, { method: "GET" });
  const body = await response.json();

  console.log("✅ Request completed\n");
  console.log("Response body:", body);

  if (response.ok) {
    const paymentResponse = new x402HTTPClient(client).getPaymentSettleResponse(name =>
      response.headers.get(name),
    );
    if (paymentResponse) {
      console.log("\n💰 Payment Details:", paymentResponse);
    }
  }
}
