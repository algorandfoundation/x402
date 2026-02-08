import { config } from "dotenv";
import { paymentMiddleware, x402ResourceServer } from "@x402/hono";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { ExactSvmScheme } from "@x402/svm/exact/server";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { Hono } from "hono";
import { serve } from "@hono/node-server";
config();

const evmAddress = process.env.EVM_ADDRESS as `0x${string}`;
const svmAddress = process.env.SVM_ADDRESS;
const avmAddress = process.env.AVM_ADDRESS;
if (!evmAddress || !svmAddress) {
  console.error("Missing required environment variables");
  process.exit(1);
}

const facilitatorUrl = process.env.FACILITATOR_URL;
if (!facilitatorUrl) {
  console.error("❌ FACILITATOR_URL environment variable is required");
  process.exit(1);
}
const facilitatorClient = new HTTPFacilitatorClient({ url: facilitatorUrl });

const accepts: { scheme: string; price: string; network: `${string}:${string}`; payTo: string }[] = [
  {
    scheme: "exact",
    price: "$0.001",
    network: "eip155:84532",
    payTo: evmAddress,
  },
  {
    scheme: "exact",
    price: "$0.001",
    network: "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
    payTo: svmAddress,
  },
];

const server = new x402ResourceServer(facilitatorClient)
  .register("eip155:84532", new ExactEvmScheme())
  .register("solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", new ExactSvmScheme());

// Register AVM (Algorand) support if configured
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
}

const app = new Hono();

app.use(
  paymentMiddleware(
    {
      "GET /weather": {
        accepts,
        description: "Weather data",
        mimeType: "application/json",
      },
    },
    server,
  ),
);

app.get("/weather", c => {
  return c.json({
    report: {
      weather: "sunny",
      temperature: 70,
    },
  });
});

serve({
  fetch: app.fetch,
  port: 4021,
});

console.log(`Server listening at http://localhost:4021`);
