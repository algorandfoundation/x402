import { config } from "dotenv";
import express from "express";
import { paymentMiddleware, x402ResourceServer } from "@x402/express";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { HTTPFacilitatorClient } from "@x402/core/server";
config();

const evmAddress = process.env.EVM_ADDRESS as `0x${string}`;
const avmAddress = process.env.AVM_ADDRESS;

const addressLookup = {
  US: evmAddress,
  UK: evmAddress,
  CA: evmAddress,
  AU: evmAddress,
  NZ: evmAddress,
  IE: evmAddress,
  FR: evmAddress,
} as Record<string, `0x${string}`>;

if (!evmAddress) {
  console.error("Missing required environment variables");
  process.exit(1);
}

const facilitatorUrl = process.env.FACILITATOR_URL;
if (!facilitatorUrl) {
  console.error("❌ FACILITATOR_URL environment variable is required");
  process.exit(1);
}
const facilitatorClient = new HTTPFacilitatorClient({ url: facilitatorUrl });

const accepts: {
  scheme: string;
  price: string;
  network: `${string}:${string}`;
  payTo: string | ((context: { adapter: { getQueryParam?: (param: string) => string | undefined } }) => string);
}[] = [
  {
    scheme: "exact",
    price: "$0.001",
    network: "eip155:84532",
    payTo: context => {
      // Dynamic payTo based on HTTP request context
      const country = context.adapter.getQueryParam?.("country") ?? "US";
      return addressLookup[country as keyof typeof addressLookup];
    },
  },
];

const server = new x402ResourceServer(facilitatorClient).register("eip155:84532", new ExactEvmScheme());

// Register AVM (Algorand) support if configured
if (avmAddress) {
  const { ExactAvmScheme } = await import("@x402/avm/exact/server");
  const { ALGORAND_TESTNET_CAIP2 } = await import("@x402/avm");

  const avmAddressLookup = {
    US: avmAddress,
    UK: avmAddress,
    CA: avmAddress,
    AU: avmAddress,
    NZ: avmAddress,
    IE: avmAddress,
    FR: avmAddress,
  } as Record<string, string>;

  accepts.push({
    scheme: "exact",
    price: "$0.001",
    network: ALGORAND_TESTNET_CAIP2,
    payTo: context => {
      const country = context.adapter.getQueryParam?.("country") ?? "US";
      return avmAddressLookup[country] || avmAddress;
    },
  });
  server.register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme());
}

const app = express();

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

app.get("/weather", (req, res) => {
  res.send({
    report: {
      weather: "sunny",
      temperature: 70,
    },
  });
});

app.listen(4021, () => {
  console.log(`Server listening at http://localhost:${4021}`);
});
