import { x402Client, wrapFetchWithPayment, x402HTTPClient } from "@x402/fetch";

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
 * @param evmPrivateKey - The EVM private key for signing (optional)
 * @param svmPrivateKey - The SVM private key for signing (optional)
 * @param avmMnemonic - The AVM mnemonic for signing (optional)
 * @param url - The URL to make the request to
 */
export async function runBuilderPatternExample(
  evmPrivateKey: `0x${string}` | undefined,
  svmPrivateKey: string | undefined,
  avmMnemonic: string | undefined,
  url: string,
): Promise<void> {
  console.log("🔧 Creating client with builder pattern...\n");

  // Builder pattern allows fine-grained control over network registration
  // More specific patterns (e.g., "eip155:1") take precedence over wildcards (e.g., "eip155:*")
  const client = new x402Client();
  const enabledNetworks: string[] = [];

  // Conditionally add EVM support
  if (evmPrivateKey) {
    const { privateKeyToAccount } = await import("viem/accounts");
    const { ExactEvmScheme } = await import("@x402/evm/exact/client");

    const evmSigner = privateKeyToAccount(evmPrivateKey);
    const ethereumMainnetSigner = evmSigner; // Could be a different signer for mainnet

    client.register("eip155:*", new ExactEvmScheme(evmSigner)); // All EVM networks
    client.register("eip155:1", new ExactEvmScheme(ethereumMainnetSigner)); // Ethereum mainnet override
    enabledNetworks.push("eip155:* (all EVM) with default signer");
    enabledNetworks.push("eip155:1 (Ethereum mainnet) with mainnet signer");
  }

  // Conditionally add SVM support
  if (svmPrivateKey) {
    const { ExactSvmScheme } = await import("@x402/svm/exact/client");
    const { createKeyPairSignerFromBytes } = await import("@solana/kit");
    const { base58 } = await import("@scure/base");

    const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
    const solanaDevnetSigner = svmSigner; // Could be a different signer for devnet

    client.register("solana:*", new ExactSvmScheme(svmSigner)); // All Solana networks
    client.register("solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", new ExactSvmScheme(solanaDevnetSigner)); // Devnet override
    enabledNetworks.push("solana:* (all Solana) with default signer");
    enabledNetworks.push("solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1 (devnet) with devnet signer");
  }

  // Conditionally add AVM (Algorand) support
  if (avmMnemonic) {
    const { ExactAvmScheme } = await import("@x402/avm/exact/client");
    const { toClientAvmSigner, mnemonicToAlgorandAccount, ALGORAND_TESTNET_CAIP2 } = await import("@x402/avm");

    // Supports both 24-word BIP-39 and 25-word Algorand native mnemonics
    const avmAccount = mnemonicToAlgorandAccount(avmMnemonic);
    const avmSigner = toClientAvmSigner(avmAccount);
    const algorandTestnetSigner = avmSigner; // Could be a different signer for testnet

    client.register("algorand:*", new ExactAvmScheme(avmSigner)); // All Algorand networks
    client.register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme(algorandTestnetSigner)); // Testnet override
    enabledNetworks.push("algorand:* (all Algorand) with default signer");
    enabledNetworks.push(`${ALGORAND_TESTNET_CAIP2} (testnet) with testnet signer`);
  }

  console.log("Registered networks:");
  enabledNetworks.forEach(network => {
    console.log(`  - ${network}`);
  });
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
