import { x402Facilitator } from "@x402/core/facilitator";
import {
  PaymentPayload,
  PaymentRequirements,
  SettleResponse,
  VerifyResponse,
} from "@x402/core/types";
import dotenv from "dotenv";
import express from "express";

dotenv.config();

// Configuration
const PORT = process.env.PORT || "4022";

// Track which networks are enabled
const enabledNetworks: string[] = [];

// Validate at least one network is configured
if (!process.env.EVM_PRIVATE_KEY && !process.env.SVM_PRIVATE_KEY && !process.env.AVM_PRIVATE_KEY) {
  console.error("❌ At least one of EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, or AVM_PRIVATE_KEY must be set");
  process.exit(1);
}

// Initialize the x402 Facilitator
const facilitator = new x402Facilitator()
  .onBeforeVerify(async (context) => {
    console.log("Before verify", context);
  })
  .onAfterVerify(async (context) => {
    console.log("After verify", context);
  })
  .onVerifyFailure(async (context) => {
    console.log("Verify failure", context);
  })
  .onBeforeSettle(async (context) => {
    console.log("Before settle", context);
  })
  .onAfterSettle(async (context) => {
    console.log("After settle", context);
  })
  .onSettleFailure(async (context) => {
    console.log("Settle failure", context);
  });

// Conditionally initialize EVM support
if (process.env.EVM_PRIVATE_KEY) {
  const { toFacilitatorEvmSigner } = await import("@x402/evm");
  const { registerExactEvmScheme } = await import("@x402/evm/exact/facilitator");
  const { createWalletClient, http, publicActions } = await import("viem");
  const { privateKeyToAccount } = await import("viem/accounts");
  const { baseSepolia } = await import("viem/chains");

  const evmAccount = privateKeyToAccount(process.env.EVM_PRIVATE_KEY as `0x${string}`);
  console.info(`EVM Facilitator account: ${evmAccount.address}`);

  const viemClient = createWalletClient({
    account: evmAccount,
    chain: baseSepolia,
    transport: http(),
  }).extend(publicActions);

  const evmSigner = toFacilitatorEvmSigner({
    getCode: (args: { address: `0x${string}` }) => viemClient.getCode(args),
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
      }),
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
      }),
    sendTransaction: (args: { to: `0x${string}`; data: `0x${string}` }) =>
      viemClient.sendTransaction(args),
    waitForTransactionReceipt: (args: { hash: `0x${string}` }) =>
      viemClient.waitForTransactionReceipt(args),
  });

  registerExactEvmScheme(facilitator, {
    signer: evmSigner,
    networks: "eip155:84532", // Base Sepolia
    deployERC4337WithEIP6492: true,
  });
  enabledNetworks.push("EVM (Base Sepolia)");
}

// Conditionally initialize SVM support
if (process.env.SVM_PRIVATE_KEY) {
  const { base58 } = await import("@scure/base");
  const { createKeyPairSignerFromBytes } = await import("@solana/kit");
  const { toFacilitatorSvmSigner } = await import("@x402/svm");
  const { registerExactSvmScheme } = await import("@x402/svm/exact/facilitator");

  const svmAccount = await createKeyPairSignerFromBytes(
    base58.decode(process.env.SVM_PRIVATE_KEY as string),
  );
  console.info(`SVM Facilitator account: ${svmAccount.address}`);

  const svmSigner = toFacilitatorSvmSigner(svmAccount);

  registerExactSvmScheme(facilitator, {
    signer: svmSigner,
    networks: "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", // Devnet
  });
  enabledNetworks.push("SVM (Solana Devnet)");
}

// Conditionally initialize AVM (Algorand) support
if (process.env.AVM_PRIVATE_KEY) {
  const { ALGORAND_TESTNET_CAIP2, DEFAULT_ALGOD_TESTNET } = await import("@x402/avm");
  const { registerExactAvmScheme } = await import("@x402/avm/exact/facilitator");
  const algosdk = await import("algosdk");

  // Decode Base64 private key (64 bytes: 32-byte seed + 32-byte public key)
  const secretKey = Buffer.from(process.env.AVM_PRIVATE_KEY as string, "base64");
  if (secretKey.length !== 64) {
    throw new Error("AVM_PRIVATE_KEY must be a Base64-encoded 64-byte key");
  }
  const address = algosdk.encodeAddress(secretKey.slice(32));
  console.info(`AVM Facilitator account: ${address}`);

  // Create Algod client for testnet
  const algodClient = new algosdk.Algodv2("", DEFAULT_ALGOD_TESTNET, "");

  // Implement FacilitatorAvmSigner interface directly
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

  registerExactAvmScheme(facilitator, {
    signer: avmSigner,
    networks: ALGORAND_TESTNET_CAIP2, // Algorand Testnet
  });
  enabledNetworks.push("AVM (Algorand Testnet)");
}

console.info(`Enabled networks: ${enabledNetworks.join(", ")}`);

// Initialize Express app
const app = express();
app.use(express.json());

/**
 * POST /verify
 * Verify a payment against requirements
 *
 * Note: Payment tracking and bazaar discovery are handled by lifecycle hooks
 */
app.post("/verify", async (req, res) => {
  try {
    const { paymentPayload, paymentRequirements } = req.body as {
      paymentPayload: PaymentPayload;
      paymentRequirements: PaymentRequirements;
    };

    if (!paymentPayload || !paymentRequirements) {
      return res.status(400).json({
        error: "Missing paymentPayload or paymentRequirements",
      });
    }

    // Hooks will automatically:
    // - Track verified payment (onAfterVerify)
    // - Extract and catalog discovery info (onAfterVerify)
    const response: VerifyResponse = await facilitator.verify(
      paymentPayload,
      paymentRequirements,
    );

    res.json(response);
  } catch (error) {
    console.error("Verify error:", error);
    res.status(500).json({
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

/**
 * POST /settle
 * Settle a payment on-chain
 *
 * Note: Verification validation and cleanup are handled by lifecycle hooks
 */
app.post("/settle", async (req, res) => {
  try {
    const { paymentPayload, paymentRequirements } = req.body;

    if (!paymentPayload || !paymentRequirements) {
      return res.status(400).json({
        error: "Missing paymentPayload or paymentRequirements",
      });
    }

    // Hooks will automatically:
    // - Validate payment was verified (onBeforeSettle - will abort if not)
    // - Check verification timeout (onBeforeSettle)
    // - Clean up tracking (onAfterSettle / onSettleFailure)
    const response: SettleResponse = await facilitator.settle(
      paymentPayload as PaymentPayload,
      paymentRequirements as PaymentRequirements,
    );

    res.json(response);
  } catch (error) {
    console.error("Settle error:", error);

    // Check if this was an abort from hook
    if (
      error instanceof Error &&
      error.message.includes("Settlement aborted:")
    ) {
      // Return a proper SettleResponse instead of 500 error
      return res.json({
        success: false,
        errorReason: error.message.replace("Settlement aborted: ", ""),
        network: req.body?.paymentPayload?.network || "unknown",
      } as SettleResponse);
    }

    res.status(500).json({
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

/**
 * GET /supported
 * Get supported payment kinds and extensions
 */
app.get("/supported", async (req, res) => {
  try {
    const response = facilitator.getSupported();
    res.json(response);
  } catch (error) {
    console.error("Supported error:", error);
    res.status(500).json({
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Start the server
app.listen(parseInt(PORT), () => {
  console.log("Facilitator listening");
});
