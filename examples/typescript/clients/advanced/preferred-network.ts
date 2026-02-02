import { x402Client, type PaymentRequirements } from "@x402/fetch";
import { x402HTTPClient, wrapFetchWithPayment } from "@x402/fetch";

/**
 * Preferred Network Example
 *
 * This demonstrates how to configure client-side payment option preferences.
 * The client can specify which network/scheme it prefers, with automatic
 * fallback to other supported options if the preferred one isn't available.
 *
 * Use cases:
 * - Prefer specific networks or chains
 * - User preference settings in a wallet UI
 *
 * @param evmPrivateKey - The EVM private key for signing (optional)
 * @param svmPrivateKey - The SVM private key for signing (optional)
 * @param avmMnemonic - The AVM mnemonic for signing (optional)
 * @param url - The URL to make the request to
 */
export async function runPreferredNetworkExample(
  evmPrivateKey: `0x${string}` | undefined,
  svmPrivateKey: string | undefined,
  avmMnemonic: string | undefined,
  url: string,
): Promise<void> {
  console.log("🎯 Creating client with preferred network selection...\n");

  // Define network preference order (most preferred first)
  // Algorand is preferred, then Solana, then EVM
  const networkPreferences = ["algorand:", "solana:", "eip155:"];

  /**
   * Custom selector that picks payment options based on preference order.
   *
   * NOTE: By the time this selector is called, `options` has already been
   * filtered to only include options that BOTH the server offers AND the
   * client has registered support for. So fallback to options[0] means
   * "first mutually-supported option" (which preserves server's preference order).
   *
   * @param _x402Version - The x402 protocol version
   * @param options - Array of mutually supported payment options
   * @returns The selected payment requirement based on network preference
   */
  const preferredNetworkSelector = (
    _x402Version: number,
    options: PaymentRequirements[],
  ): PaymentRequirements => {
    console.log("📋 Mutually supported payment options (server offers + client supports):");
    options.forEach((opt, i) => {
      console.log(`   ${i + 1}. ${opt.network} (${opt.scheme})`);
    });
    console.log();

    // Try each preference in order
    for (const preference of networkPreferences) {
      const match = options.find(opt => opt.network.startsWith(preference));
      if (match) {
        console.log(`✨ Selected preferred network: ${match.network}`);
        return match;
      }
    }

    // Fallback to first mutually-supported option (server's top preference among what we support)
    console.log(`⚠️  No preferred network available, falling back to: ${options[0].network}`);
    return options[0];
  };

  const client = new x402Client(preferredNetworkSelector);
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
  console.log(`Network preference order: ${networkPreferences.join(" > ")}\n`);

  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  console.log(`🌐 Making request to: ${url}\n`);
  const response = await fetchWithPayment(url, { method: "GET" });
  const body = await response.json();

  console.log("✅ Request completed successfully\n");
  console.log("Response body:", body);

  // Extract payment response from headers
  const paymentResponse = new x402HTTPClient(client).getPaymentSettleResponse(name =>
    response.headers.get(name),
  );
  if (paymentResponse) {
    console.log("\n💰 Payment Details:", paymentResponse);
  }
}
