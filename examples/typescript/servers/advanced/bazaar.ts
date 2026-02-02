import { config } from "dotenv";
import express from "express";
import { paymentMiddleware, x402ResourceServer } from "@x402/express";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { declareDiscoveryExtension } from "@x402/extensions/bazaar";
config();

// Configuration
const evmAddress = process.env.EVM_ADDRESS as `0x${string}`;
const svmAddress = process.env.SVM_ADDRESS;
const avmAddress = process.env.AVM_ADDRESS;
const port = parseInt(process.env.PORT || "4021", 10);

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
type AcceptConfig = { scheme: string; price: string; network: `${string}:${string}`; payTo: string };
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
    payTo: evmAddress,
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
    payTo: svmAddress,
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
    payTo: avmAddress,
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
        description: "Weather data",
        mimeType: "application/json",
        extensions: {
          ...declareDiscoveryExtension({
            input: { city: "San Francisco" },
            inputSchema: {
              properties: {
                city: { type: "string" },
              },
              required: ["city"],
            },
            output: {
              example: {
                city: "San Francisco",
                weather: "foggy",
                temperature: 60,
              },
            },
          }),
        },
      },
    },
    server,
  ),
);

app.get("/weather", (req, res) => {
  console.log("  Resource accessed - payment verified and settled");
  const city = (req.query.city as string) || "San Francisco";

  const weatherData: Record<string, { weather: string; temperature: number }> = {
    "San Francisco": { weather: "foggy", temperature: 60 },
    "New York": { weather: "cloudy", temperature: 55 },
  };

  const data = weatherData[city] || { weather: "sunny", temperature: 70 };

  res.send({
    city,
    weather: data.weather,
    temperature: data.temperature,
  });
});

app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});
