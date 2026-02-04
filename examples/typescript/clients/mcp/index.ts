/**
 * MCP Server with x402 Payment Integration
 *
 * This example demonstrates how to create an MCP server that can make
 * paid API requests using the x402 protocol with EVM, SVM, and AVM support.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import axios from "axios";
import { config } from "dotenv";
import { x402Client, wrapAxiosWithPayment } from "@x402/axios";

config();

const evmPrivateKey = process.env.EVM_PRIVATE_KEY as `0x${string}`;
const svmPrivateKey = process.env.SVM_PRIVATE_KEY as string;
const avmMnemonic = process.env.AVM_MNEMONIC as string;
const baseURL = process.env.RESOURCE_SERVER_URL || "http://localhost:4021";
const endpointPath = process.env.ENDPOINT_PATH || "/weather";

if (!evmPrivateKey && !svmPrivateKey && !avmMnemonic) {
  throw new Error("At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_MNEMONIC must be provided");
}

/**
 * Creates an axios client configured with x402 payment support for EVM, SVM, and/or AVM.
 *
 * @returns A wrapped axios instance that handles 402 payment flows automatically.
 */
async function createClient() {
  const client = new x402Client();
  const enabledNetworks: string[] = [];

  // Conditionally register EVM scheme
  if (evmPrivateKey) {
    const { registerExactEvmScheme } = await import("@x402/evm/exact/client");
    const { privateKeyToAccount } = await import("viem/accounts");
    const evmSigner = privateKeyToAccount(evmPrivateKey);
    registerExactEvmScheme(client, { signer: evmSigner });
    enabledNetworks.push("EVM");
  }

  // Conditionally register SVM scheme
  if (svmPrivateKey) {
    const { registerExactSvmScheme } = await import("@x402/svm/exact/client");
    const { createKeyPairSignerFromBytes } = await import("@solana/kit");
    const { base58 } = await import("@scure/base");
    const svmSigner = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
    registerExactSvmScheme(client, { signer: svmSigner });
    enabledNetworks.push("SVM");
  }

  // Conditionally register AVM scheme
  if (avmMnemonic) {
    const { registerExactAvmScheme } = await import("@x402/avm/exact/client");
    const { toClientAvmSigner, mnemonicToAlgorandAccount } = await import("@x402/avm");
    // Supports both 24-word BIP-39 and 25-word Algorand native mnemonics
    const avmAccount = mnemonicToAlgorandAccount(avmMnemonic);
    const avmSigner = toClientAvmSigner(avmAccount);
    registerExactAvmScheme(client, { signer: avmSigner });
    enabledNetworks.push("AVM");
  }

  console.error(`x402 MCP Client initialized with networks: ${enabledNetworks.join(", ")}`);

  return wrapAxiosWithPayment(axios.create({ baseURL }), client);
}

/**
 * Initializes and starts the MCP server with x402 payment-enabled tools.
 */
async function main() {
  const api = await createClient();

  // Create an MCP server
  const server = new McpServer({
    name: "x402 MCP Client Demo",
    version: "2.0.0",
  });

  // Add a tool to get data from the resource server
  server.tool(
    "get-data-from-resource-server",
    "Get data from the resource server",
    {},
    async () => {
      const res = await api.get(endpointPath);
      return {
        content: [{ type: "text", text: JSON.stringify(res.data) }],
      };
    },
  );

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
