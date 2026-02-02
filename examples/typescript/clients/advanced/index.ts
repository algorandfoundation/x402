import { config } from "dotenv";
import { runHooksExample } from "./hooks";
import { runPreferredNetworkExample } from "./preferred-network";
import { runBuilderPatternExample } from "./builder-pattern";

config();

const evmPrivateKey = process.env.EVM_PRIVATE_KEY as `0x${string}`;
const svmPrivateKey = process.env.SVM_PRIVATE_KEY as string;
const avmMnemonic = process.env.AVM_MNEMONIC as string;
const baseURL = process.env.RESOURCE_SERVER_URL || "http://localhost:4021";
const endpointPath = process.env.ENDPOINT_PATH || "/weather";
const url = `${baseURL}${endpointPath}`;

/**
 * Main example runner for advanced x402 client patterns.
 *
 * This package demonstrates advanced patterns for production-ready x402 clients:
 *
 * - builder-pattern: Fine-grained control over network registration
 * - hooks: Payment lifecycle hooks for custom logic at different stages
 * - preferred-network: Client-side payment network preferences
 *
 * To run this example, you need to set at least one of the following environment variables:
 * - EVM_PRIVATE_KEY: The private key of the EVM signer
 * - SVM_PRIVATE_KEY: The private key of the SVM signer
 * - AVM_MNEMONIC: The 25-word mnemonic phrase for the Algorand signer
 *
 * Usage:
 *   pnpm start builder-pattern
 *   pnpm start hooks
 *   pnpm start preferred-network
 */
async function main(): Promise<void> {
  const pattern = process.argv[2] || "builder-pattern";

  console.log(`\n🚀 Running advanced example: ${pattern}\n`);

  // Validate at least one network is configured
  if (!evmPrivateKey && !svmPrivateKey && !avmMnemonic) {
    console.error("❌ At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_MNEMONIC must be set");
    process.exit(1);
  }

  switch (pattern) {
    case "builder-pattern":
      await runBuilderPatternExample(evmPrivateKey, svmPrivateKey, avmMnemonic, url);
      break;

    case "hooks":
      await runHooksExample(evmPrivateKey, svmPrivateKey, avmMnemonic, url);
      break;

    case "preferred-network":
      await runPreferredNetworkExample(evmPrivateKey, svmPrivateKey, avmMnemonic, url);
      break;

    default:
      console.error(`Unknown pattern: ${pattern}`);
      console.error("Available patterns: builder-pattern, hooks, preferred-network");
      process.exit(1);
  }
}

main().catch(error => {
  console.error(error?.response?.data?.error ?? error);
  process.exit(1);
});
