import { paymentProxy } from "@x402/next";
import { x402ResourceServer, HTTPFacilitatorClient } from "@x402/core/server";
import { createPaywall } from "@x402/paywall";
import { declareDiscoveryExtension } from "@x402/extensions/bazaar";

const facilitatorUrl = process.env.FACILITATOR_URL;
export const evmAddress = process.env.EVM_ADDRESS as `0x${string}`;
export const svmAddress = process.env.SVM_ADDRESS;
export const avmAddress = process.env.AVM_ADDRESS;

if (!facilitatorUrl) {
  console.error("❌ FACILITATOR_URL environment variable is required");
  process.exit(1);
}

// Validate at least one network address is configured
if (!evmAddress && !svmAddress && !avmAddress) {
  console.error("❌ At least one of EVM_ADDRESS, SVM_ADDRESS, or AVM_ADDRESS must be set");
  process.exit(1);
}

// Create HTTP facilitator client
const facilitatorClient = new HTTPFacilitatorClient({ url: facilitatorUrl });

// Create x402 resource server
export const server = new x402ResourceServer(facilitatorClient);

// Build accepts array and paywall based on available addresses
type AcceptConfig = { scheme: string; price: string; network: `${string}:${string}`; payTo: string };
export const accepts: AcceptConfig[] = [];
const paywallBuilder = createPaywall();
const enabledNetworks: string[] = [];

// Conditionally add EVM support
if (evmAddress) {
  const { registerExactEvmScheme } = await import("@x402/evm/exact/server");
  const { evmPaywall } = await import("@x402/paywall/evm");
  const network = "eip155:84532" as const; // Base Sepolia

  registerExactEvmScheme(server);
  accepts.push({
    scheme: "exact",
    price: "$0.001",
    network,
    payTo: evmAddress,
  });
  paywallBuilder.withNetwork(evmPaywall);
  enabledNetworks.push("EVM (Base Sepolia)");
  console.info(`EVM address: ${evmAddress}`);
}

// Conditionally add SVM support
if (svmAddress) {
  const { registerExactSvmScheme } = await import("@x402/svm/exact/server");
  const { svmPaywall } = await import("@x402/paywall/svm");
  const network = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1" as const; // Solana Devnet

  registerExactSvmScheme(server);
  accepts.push({
    scheme: "exact",
    price: "$0.001",
    network,
    payTo: svmAddress,
  });
  paywallBuilder.withNetwork(svmPaywall);
  enabledNetworks.push("SVM (Solana Devnet)");
  console.info(`SVM address: ${svmAddress}`);
}

// Conditionally add AVM (Algorand) support
if (avmAddress) {
  const { registerExactAvmScheme } = await import("@x402/avm/exact/server");
  const { avmPaywall } = await import("@x402/paywall/avm");
  const { ALGORAND_TESTNET_CAIP2 } = await import("@x402/avm");

  registerExactAvmScheme(server);
  accepts.push({
    scheme: "exact",
    price: "$0.001",
    network: ALGORAND_TESTNET_CAIP2,
    payTo: avmAddress,
  });
  paywallBuilder.withNetwork(avmPaywall);
  enabledNetworks.push("AVM (Algorand Testnet)");
  console.info(`AVM address: ${avmAddress}`);
}

console.info(`Enabled networks: ${enabledNetworks.join(", ")}`);

// Build paywall
export const paywall = paywallBuilder
  .withConfig({
    appName: process.env.APP_NAME || "Next x402 Demo",
    appLogo: process.env.APP_LOGO || "/x402-icon-blue.png",
    testnet: true,
  })
  .build();

// Build proxy
export const proxy = paymentProxy(
  {
    "/protected": {
      accepts,
      description: "Premium music: x402 Remix",
      mimeType: "text/html",
      extensions: {
        ...declareDiscoveryExtension({}),
      },
    },
  },
  server,
  undefined, // paywallConfig (using custom paywall instead)
  paywall, // custom paywall provider
);

// Configure which paths the proxy should run on
export const config = {
  matcher: ["/protected/:path*"],
};
