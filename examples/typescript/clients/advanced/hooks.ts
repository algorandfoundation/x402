import { privateKeyToAccount } from "viem/accounts";
import { x402Client } from "@x402/fetch";
import { ExactEvmScheme } from "@x402/evm/exact/client";

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
 * @param evmPrivateKey - The EVM private key for signing
 * @param url - The URL to make the request to
 */
export async function runHooksExample(
  evmPrivateKey: `0x${string}`,
  avmPrivateKey: string | undefined,
  url: string,
): Promise<void> {
  console.log("🔧 Creating client with payment lifecycle hooks...\n");

  const evmSigner = privateKeyToAccount(evmPrivateKey);

  const client = new x402Client()
    .register("eip155:*", new ExactEvmScheme(evmSigner))
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

  // Register AVM (Algorand) support if configured
  if (avmPrivateKey) {
    const { ExactAvmScheme } = await import("@x402/avm/exact/client");
    const algosdk = await import("algosdk");

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

    client.register("algorand:*", new ExactAvmScheme(avmSigner));
  }

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
