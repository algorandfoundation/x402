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
import { ALGORAND_TESTNET_CAIP2, DEFAULT_ALGOD_TESTNET } from "@x402/avm";
import algosdk from "algosdk";
import { ExactAvmScheme } from "@x402/avm/exact/facilitator";
import { ExactAvmSchemeV1 } from "@x402/avm/exact/v1/facilitator";
import { createWalletClient, http, publicActions } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { baseSepolia } from "viem/chains";

/**
 * Initialize and configure the x402 facilitator with EVM and SVM support
 * This is called lazily on first use to support Next.js module loading
 *
 * @returns A configured x402Facilitator instance
 */
async function createFacilitator(): Promise<x402Facilitator> {
  // Validate required environment variables
  if (!process.env.FACILITATOR_EVM_PRIVATE_KEY) {
    throw new Error("❌ FACILITATOR_EVM_PRIVATE_KEY environment variable is required");
  }

  if (!process.env.FACILITATOR_SVM_PRIVATE_KEY) {
    throw new Error("❌ FACILITATOR_SVM_PRIVATE_KEY environment variable is required");
  }

  // Initialize the EVM account from private key
  const evmAccount = privateKeyToAccount(process.env.FACILITATOR_EVM_PRIVATE_KEY as `0x${string}`);

  // Create a Viem client with both wallet and public capabilities
  const viemClient = createWalletClient({
    account: evmAccount,
    chain: baseSepolia,
    transport: http(),
  }).extend(publicActions);

  // Initialize the x402 Facilitator with EVM signer
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

  // Initialize the SVM account from private key
  const svmAccount = await createKeyPairSignerFromBytes(
    base58.decode(process.env.FACILITATOR_SVM_PRIVATE_KEY as string),
  );

  // Initialize SVM signer - handles all Solana networks with automatic RPC creation
  const svmSigner = toFacilitatorSvmSigner(svmAccount);

  // Create and configure the facilitator
  const facilitator = new x402Facilitator()
    .register("eip155:84532", new ExactEvmScheme(evmSigner))
    .registerV1("base-sepolia" as Network, new ExactEvmSchemeV1(evmSigner))
    .register("solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", new ExactSvmScheme(svmSigner))
    .registerV1("solana-devnet" as Network, new ExactSvmSchemeV1(svmSigner));

  // Register AVM (Algorand) support if configured
  const avmPrivateKey = process.env.FACILITATOR_AVM_PRIVATE_KEY || process.env.PRIVATE_KEY;
  if (avmPrivateKey) {
    try {
      const secretKey = Buffer.from(avmPrivateKey, "base64");
      if (secretKey.length !== 64) {
        throw new Error("FACILITATOR_AVM_PRIVATE_KEY must be a Base64-encoded 64-byte key");
      }
      const address = algosdk.encodeAddress(secretKey.slice(32));

      const algodClient = new algosdk.Algodv2("", DEFAULT_ALGOD_TESTNET, "");

      const avmSigner = {
        getAddresses: () => [address] as readonly string[],

        signTransaction: async (txn: Uint8Array, _senderAddress: string) => {
          const decoded = algosdk.decodeUnsignedTransaction(txn);
          const signed = algosdk.signTransaction(decoded, secretKey);
          return signed.blob;
        },

        getAlgodClient: (_network: string) => algodClient,

        simulateTransactions: async (txns: Uint8Array[], _network: string) => {
          const request = new algosdk.modelsv2.SimulateRequest({
            txnGroups: [
              new algosdk.modelsv2.SimulateRequestTransactionGroup({
                txns: txns.map(txn => algosdk.decodeSignedTransaction(txn)),
              }),
            ],
            allowUnnamedResources: true,
          });
          return await algodClient.simulateTransactions(request).do();
        },

        sendTransactions: async (signedTxns: Uint8Array[], _network: string) => {
          const response = await algodClient.sendRawTransaction(signedTxns).do();
          return response.txid;
        },

        waitForConfirmation: async (txId: string, _network: string, waitRounds: number = 4) => {
          return await algosdk.waitForConfirmation(algodClient, txId, waitRounds);
        },
      };

      facilitator
        .register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme(avmSigner))
        .registerV1("algorand-testnet" as Network, new ExactAvmSchemeV1(avmSigner));

      console.log(`✅ AVM (Algorand) facilitator initialized for address: ${address}`);
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
