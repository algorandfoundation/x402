import { config } from "dotenv";
import express from "express";
import { paymentMiddleware, x402ResourceServer } from "@x402/express";
import { HTTPFacilitatorClient } from "@x402/core/server";
config();

// Configuration
const evmAddress = process.env.EVM_ADDRESS as `0x${string}`;
const svmAddress = process.env.SVM_ADDRESS;
const avmAddress = process.env.AVM_ADDRESS;
const port = parseInt(process.env.PORT || "4021", 10);

// Dynamic payTo address lookups per network (for demonstration, all countries use the same address)
// In production, you could have different addresses per country/region for each network
const evmAddressLookup = {
  US: evmAddress,
  UK: evmAddress,
  CA: evmAddress,
  AU: evmAddress,
  NZ: evmAddress,
  IE: evmAddress,
  FR: evmAddress,
} as Record<string, `0x${string}`>;

const svmAddressLookup = {
  US: svmAddress,
  UK: svmAddress,
  CA: svmAddress,
  AU: svmAddress,
  NZ: svmAddress,
  IE: svmAddress,
  FR: svmAddress,
} as Record<string, string>;

const avmAddressLookup = {
  US: avmAddress,
  UK: avmAddress,
  CA: avmAddress,
  AU: avmAddress,
  NZ: avmAddress,
  IE: avmAddress,
  FR: avmAddress,
} as Record<string, string>;

// Validate at least one network address is configured
if (!evmAddress && !svmAddress && !avmAddress) {
  console.error("❌ At least one of EVM_ADDRESS, SVM_ADDRESS, or AVM_ADDRESS must be set");
  process.exit(1);
}

const facilitatorUrl = process.env.FACILITATOR_URL;
if (!facilitatorUrl) {
  console.error("❌ FACILITATOR_URL environment variable is required");
  process.exit(1);
}
const facilitatorClient = new HTTPFacilitatorClient({ url: facilitatorUrl });

// Build accepts array and register schemes based on available addresses
type AcceptConfig = {
  scheme: string;
  price: string;
  network: `${string}:${string}`;
  payTo: string | ((context: { adapter: { getQueryParam?: (param: string) => string | undefined } }) => string);
};
const accepts: AcceptConfig[] = [];
const server = new x402ResourceServer(facilitatorClient);
const enabledNetworks: string[] = [];

// Conditionally add EVM support
if (evmAddress) {
  const { ExactEvmScheme } = await import("@x402/evm/exact/server");
  const network = "eip155:84532"; // Base Sepolia

  accepts.push({
    scheme: "exact",
    price: "$0.001",
    network,
    payTo: context => {
      // Dynamic payTo based on HTTP request context
      const country = context.adapter.getQueryParam?.("country") ?? "US";
      return evmAddressLookup[country] || evmAddress;
    },
  });
  server.register(network, new ExactEvmScheme());
  enabledNetworks.push("EVM (Base Sepolia)");
  console.info(`EVM address: ${evmAddress}`);
}

// Conditionally add SVM support
if (svmAddress) {
  const { ExactSvmScheme } = await import("@x402/svm/exact/server");
  const network = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"; // Solana Devnet

  accepts.push({
    scheme: "exact",
    price: "$0.001",
    network,
    payTo: context => {
      // Dynamic payTo based on HTTP request context
      const country = context.adapter.getQueryParam?.("country") ?? "US";
      return svmAddressLookup[country] || svmAddress;
    },
  });
  server.register(network, new ExactSvmScheme());
  enabledNetworks.push("SVM (Solana Devnet)");
  console.info(`SVM address: ${svmAddress}`);
}

// Conditionally add AVM (Algorand) support
if (avmAddress) {
  const { ExactAvmScheme } = await import("@x402/avm/exact/server");
  const { ALGORAND_TESTNET_CAIP2 } = await import("@x402/avm");

  accepts.push({
    scheme: "exact",
    price: "$0.001",
    network: ALGORAND_TESTNET_CAIP2,
    payTo: context => {
      // Dynamic payTo based on HTTP request context
      const country = context.adapter.getQueryParam?.("country") ?? "US";
      return avmAddressLookup[country] || avmAddress;
    },
  });
  server.register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme());
  enabledNetworks.push("AVM (Algorand Testnet)");
  console.info(`AVM address: ${avmAddress}`);
}

console.info(`Enabled networks: ${enabledNetworks.join(", ")}`);

const app = express();

// Request logging middleware
app.use((req, res, next) => {
  const start = Date.now();
  const paymentHeader = req.headers["x-payment"] || req.headers["x-payment-signature"];

  console.log(`\n→ ${req.method} ${req.path}`);
  if (paymentHeader) {
    console.log(`  Payment header present: ${typeof paymentHeader === "string" ? paymentHeader.substring(0, 50) + "..." : "yes"}`);
  }

  res.on("finish", () => {
    const duration = Date.now() - start;
    const statusIcon = res.statusCode === 200 ? "✓" : res.statusCode === 402 ? "💰" : "✗";
    console.log(`← ${statusIcon} ${res.statusCode} (${duration}ms)`);
  });

  next();
});

app.use(
  paymentMiddleware(
    {
      "GET /weather": {
        accepts,
        description: "Weather data with dynamic payTo",
        mimeType: "application/json",
      },
    },
    server,
  ),
);

app.get("/weather", (req, res) => {
  res.send({
    report: {
      weather: "sunny",
      temperature: 70,
    },
  });
});

app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});
