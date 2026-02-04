import { x402Client } from "@x402/fetch";

/**
 * Hooks Example
 *
 * This demonstrates how to register hooks for payment creation lifecycle events.
 * Hooks allow you to add custom logic at different stages:
 * - onBeforePaymentCreation: Called before payment creation starts, can abort
 * - onAfterPaymentCreation: Called after successful payment creation
 * - onPaymentCreationFailure: Called when payment creation fails, can recover
 *
 * This is an advanced feature useful for:
 * - Logging payment events for debugging and monitoring
 * - Custom validation before allowing payments
 * - Error recovery strategies
 * - Metrics and analytics collection
 *
 * @param evmPrivateKey - The EVM private key for signing (optional)
 * @param svmPrivateKey - The SVM private key for signing (optional)
 * @param avmMnemonic - The AVM mnemonic for signing (optional)
 * @param url - The URL to make the request to
 */
export async function runHooksExample(
  evmPrivateKey: `0x${string}` | undefined,
  svmPrivateKey: string | undefined,
  avmMnemonic: string | undefined,
  url: string,
): Promise<void> {
  console.log("🔧 Creating client with payment lifecycle hooks...\n");

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
    const { ExactAvmScheme } = await import("@x402/avm/exact/client");
    const { toClientAvmSigner, mnemonicToAlgorandAccount } = await import("@x402/avm");

    // Supports both 24-word BIP-39 and 25-word Algorand native mnemonics
    const avmAccount = mnemonicToAlgorandAccount(avmMnemonic);
    const avmSigner = toClientAvmSigner(avmAccount);
    client.register("algorand:*", new ExactAvmScheme(avmSigner));
    enabledNetworks.push("AVM (algorand:*)");
  }

  console.log(`Enabled networks: ${enabledNetworks.join(", ")}\n`);

  // Add lifecycle hooks
  client
    .onBeforePaymentCreation(async context => {
      console.log("🔍 [BeforePaymentCreation] Creating payment for:");
      console.log(`   Network: ${context.selectedRequirements.network}`);
      console.log(`   Scheme: ${context.selectedRequirements.scheme}`);
      console.log();

      // You can abort payment creation by returning:
      // return { abort: true, reason: "Payment not allowed for this resource" };
    })
    .onAfterPaymentCreation(async context => {
      console.log("✅ [AfterPaymentCreation] Payment created successfully");
      console.log(`   Version: ${context.paymentPayload.x402Version}`);
      console.log();

      // Perform side effects like logging to database, sending metrics, etc.
      // Errors here are logged but don't fail the payment
    })
    .onPaymentCreationFailure(async context => {
      console.log(`❌ [OnPaymentCreationFailure] Payment creation failed: ${context.error}`);
      console.log();

      // You could attempt to recover by providing an alternative payload:
      // return { recovered: true, payload: alternativePayload };
    });

  const { wrapFetchWithPayment } = await import("@x402/fetch");
  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  console.log(`🌐 Making request to: ${url}\n`);
  const response = await fetchWithPayment(url, { method: "GET" });
  const body = await response.json();

  console.log("✅ Request completed successfully with hooks\n");
  console.log("Response body:", body);

  // Extract payment response from headers
  const { x402HTTPClient } = await import("@x402/fetch");
  const paymentResponse = new x402HTTPClient(client).getPaymentSettleResponse(name =>
    response.headers.get(name),
  );
  if (paymentResponse) {
    console.log("\n💰 Payment Details:", paymentResponse);
  }
}
