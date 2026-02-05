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
const resourceServer = new x402ResourceServer(facilitatorClient);
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
  resourceServer.register(network, new ExactEvmScheme());
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
  resourceServer.register(network, new ExactSvmScheme());
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
  resourceServer.register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme());
  enabledNetworks.push("AVM (Algorand Testnet)");
  console.info(`AVM address: ${avmAddress}`);
}

console.info(`Enabled networks: ${enabledNetworks.join(", ")}`);

// Add lifecycle hooks
resourceServer
  .onBeforeVerify(async context => {
    console.log("Before verify hook", context);
    // Abort verification by returning { abort: true, reason: string }
  })
  .onAfterVerify(async context => {
    console.log("After verify hook", context);
  })
  .onVerifyFailure(async context => {
    console.log("Verify failure hook", context);
    // Return a result with Recovered=true to recover from the failure
    // return { recovered: true, result: { isValid: true, invalidReason: "Recovered from failure" } };
  })
  .onBeforeSettle(async context => {
    console.log("Before settle hook", context);
    // Abort settlement by returning { abort: true, reason: string }
  })
  .onAfterSettle(async context => {
    console.log("After settle hook", context);
  })
  .onSettleFailure(async context => {
    console.log("Settle failure hook", context);
    // Return a result with Recovered=true to recover from the failure
    // return { recovered: true, result: { success: true, transaction: "0x123..." } };
  });

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
      },
    },
    resourceServer,
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
