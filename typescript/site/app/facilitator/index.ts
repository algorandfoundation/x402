import { base58 } from "@scure/base";
import { createKeyPairSignerFromBytes } from "@solana/kit";
import { x402Facilitator } from "@x402/core/facilitator";
import { Network } from "@x402/core/types";
import { toFacilitatorEvmSigner } from "@x402/evm";
import { ExactEvmScheme } from "@x402/evm/exact/facilitator";
import { ExactEvmSchemeV1 } from "@x402/evm/exact/v1/facilitator";
import { toFacilitatorSvmSigner } from "@x402/svm";
import { ExactSvmScheme } from "@x402/svm/exact/facilitator";
import { ExactSvmSchemeV1 } from "@x402/svm/exact/v1/facilitator";
import { toFacilitatorAvmSigner, ALGORAND_TESTNET_CAIP2 } from "@x402/avm";
import { ExactAvmScheme } from "@x402/avm/exact/facilitator";
import { ExactAvmSchemeV1 } from "@x402/avm/exact/v1/facilitator";
import algosdk from "algosdk";
import { createWalletClient, http, publicActions } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { baseSepolia } from "viem/chains";

/**
 * Initialize and configure the x402 facilitator with EVM, SVM, and AVM support
 * This is called lazily on first use to support Next.js module loading
 *
 * @returns A configured x402Facilitator instance
 */
async function createFacilitator(): Promise<x402Facilitator> {
  // All chains are optional - at least one should be configured
  const evmPrivateKey = process.env.FACILITATOR_EVM_PRIVATE_KEY;
  const svmPrivateKey = process.env.FACILITATOR_SVM_PRIVATE_KEY;
  const avmMnemonic = process.env.FACILITATOR_AVM_MNEMONIC || process.env.PRIVATE_KEY;

  if (!evmPrivateKey && !svmPrivateKey && !avmMnemonic) {
    throw new Error(
      "❌ At least one facilitator key must be configured: FACILITATOR_EVM_PRIVATE_KEY, FACILITATOR_SVM_PRIVATE_KEY, or FACILITATOR_AVM_MNEMONIC",
    );
  }

  // Create the base facilitator
  let facilitator = new x402Facilitator();

  // Add EVM support if private key is available
  if (evmPrivateKey) {
    try {
      const evmAccount = privateKeyToAccount(evmPrivateKey as `0x${string}`);

      const viemClient = createWalletClient({
        account: evmAccount,
        chain: baseSepolia,
        transport: http(),
      }).extend(publicActions);

      const evmSigner = toFacilitatorEvmSigner({
        address: evmAccount.address,
        readContract: (args: {
          address: `0x${string}`;
          abi: readonly unknown[];
          functionName: string;
          args?: readonly unknown[];
        }) =>
          viemClient.readContract({
            ...args,
            args: args.args || [],
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
          } as any),
        verifyTypedData: (args: {
          address: `0x${string}`;
          domain: Record<string, unknown>;
          types: Record<string, unknown>;
          primaryType: string;
          message: Record<string, unknown>;
          signature: `0x${string}`;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        }) => viemClient.verifyTypedData(args as any),
        writeContract: (args: {
          address: `0x${string}`;
          abi: readonly unknown[];
          functionName: string;
          args: readonly unknown[];
        }) =>
          viemClient.writeContract({
            ...args,
            args: args.args || [],
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
          } as any),
        sendTransaction: (args: { to: `0x${string}`; data: `0x${string}` }) =>
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          viemClient.sendTransaction({ to: args.to, data: args.data } as any),
        waitForTransactionReceipt: (args: { hash: `0x${string}` }) =>
          viemClient.waitForTransactionReceipt(args),
        getCode: (args: { address: `0x${string}` }) => viemClient.getCode(args),
      });

      facilitator = facilitator
        .register("eip155:84532", new ExactEvmScheme(evmSigner))
        .registerV1("base-sepolia" as Network, new ExactEvmSchemeV1(evmSigner));

      console.log(`✅ EVM facilitator initialized for address: ${evmAccount.address}`);
    } catch (error) {
      console.warn(
        `⚠️ Failed to initialize EVM facilitator: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  // Add SVM support if private key is available
  if (svmPrivateKey) {
    try {
      const svmAccount = await createKeyPairSignerFromBytes(base58.decode(svmPrivateKey));
      const svmSigner = toFacilitatorSvmSigner(svmAccount);

      facilitator = facilitator
        .register("solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", new ExactSvmScheme(svmSigner))
        .registerV1("solana-devnet" as Network, new ExactSvmSchemeV1(svmSigner));

      console.log(`✅ SVM facilitator initialized for address: ${svmAccount.address}`);
    } catch (error) {
      console.warn(
        `⚠️ Failed to initialize SVM facilitator: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  // Add AVM (Algorand) support if mnemonic is available
  if (avmMnemonic) {
    try {
      const avmAccount = algosdk.mnemonicToSecretKey(avmMnemonic);
      const avmSigner = toFacilitatorAvmSigner(avmAccount);

      facilitator = facilitator
        .register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme(avmSigner))
        .registerV1("algorand-testnet" as Network, new ExactAvmSchemeV1(avmSigner));

      console.log(`✅ AVM (Algorand) facilitator initialized for address: ${avmAccount.addr}`);
    } catch (error) {
      console.warn(
        `⚠️ Failed to initialize AVM facilitator: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  return facilitator;
}

// Lazy initialization
let _facilitatorPromise: Promise<x402Facilitator> | null = null;

/**
 * Get the configured facilitator instance
 * Uses lazy initialization to create the facilitator on first access
 *
 * @returns A promise that resolves to the configured facilitator
 */
export async function getFacilitator(): Promise<x402Facilitator> {
  if (!_facilitatorPromise) {
    _facilitatorPromise = createFacilitator();
  }
  return _facilitatorPromise;
}
