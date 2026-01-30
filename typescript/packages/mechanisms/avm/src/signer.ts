/**
 * AVM (Algorand) Signer Types for x402 Payment Protocol
 *
 * Defines signer interfaces for client and facilitator operations.
 */

import algosdk from "algosdk";
import type { Network } from "@x402/core/types";
import {
  DEFAULT_ALGOD_MAINNET,
  DEFAULT_ALGOD_TESTNET,
  ALGORAND_MAINNET_CAIP2,
  ALGORAND_TESTNET_CAIP2,
  V1_ALGORAND_MAINNET,
  V1_ALGORAND_TESTNET,
} from "./constants";

/**
 * Client-side signer interface for Algorand wallets
 *
 * Compatible with @txnlab/use-wallet and similar wallet libraries.
 * Used to sign payment transactions on the client side.
 */
export interface ClientAvmSigner {
  /**
   * The Algorand address of the signer
   */
  address: string;

  /**
   * Sign one or more transactions
   *
   * @param txns - Array of unsigned transactions (encoded as Uint8Array)
   * @param indexesToSign - Optional array of indexes to sign (if not provided, sign all)
   * @returns Promise resolving to array of signed transactions (null for unsigned)
   */
  signTransactions(
    txns: Uint8Array[],
    indexesToSign?: number[],
  ): Promise<(Uint8Array | null)[]>;
}

/**
 * Configuration for client AVM operations
 */
export interface ClientAvmConfig {
  /**
   * Pre-configured Algod client (takes precedence)
   */
  algodClient?: algosdk.Algodv2;

  /**
   * Algod API URL (used if algodClient not provided)
   */
  algodUrl?: string;

  /**
   * Algod API token (used if algodClient not provided)
   */
  algodToken?: string;
}

/**
 * Facilitator signer interface for Algorand operations
 *
 * Used by the facilitator to verify and settle payments.
 * Supports multiple addresses for load balancing and key rotation.
 */
export interface FacilitatorAvmSigner {
  /**
   * Get all addresses this facilitator can use as fee payers
   *
   * @returns Array of Algorand addresses
   */
  getAddresses(): readonly string[];

  /**
   * Sign a transaction with the signer matching the sender address
   *
   * @param txn - Transaction bytes to sign
   * @param senderAddress - Expected sender address (for verification)
   * @returns Promise resolving to signed transaction bytes
   */
  signTransaction(txn: Uint8Array, senderAddress: string): Promise<Uint8Array>;

  /**
   * Get Algod client for a specific network
   *
   * @param network - Network identifier (CAIP-2 or V1 format)
   * @returns Algod client instance
   */
  getAlgodClient(network: Network): algosdk.Algodv2;

  /**
   * Simulate a transaction group before submission
   *
   * @param txns - Array of signed transaction bytes
   * @param network - Network identifier
   * @returns Promise resolving to simulation response
   */
  simulateTransactions(
    txns: Uint8Array[],
    network: Network,
  ): Promise<algosdk.modelsv2.SimulateResponse>;

  /**
   * Submit signed transactions to the network
   *
   * @param signedTxns - Array of signed transaction bytes
   * @param network - Network identifier
   * @returns Promise resolving to transaction ID
   */
  sendTransactions(signedTxns: Uint8Array[], network: Network): Promise<string>;

  /**
   * Wait for a transaction to be confirmed
   *
   * @param txId - Transaction ID
   * @param network - Network identifier
   * @param waitRounds - Number of rounds to wait (default: 4)
   * @returns Promise resolving to pending transaction info
   */
  waitForConfirmation(
    txId: string,
    network: Network,
    waitRounds?: number,
  ): Promise<algosdk.modelsv2.PendingTransactionResponse>;
}

/**
 * Configuration for creating a facilitator signer
 */
export interface FacilitatorAvmSignerConfig {
  /**
   * Algod client for mainnet
   */
  mainnet?: algosdk.Algodv2;

  /**
   * Algod client for testnet
   */
  testnet?: algosdk.Algodv2;

  /**
   * Default Algod URL (used as fallback)
   */
  defaultUrl?: string;

  /**
   * Default Algod token
   */
  defaultToken?: string;
}

/**
 * Creates a FacilitatorAvmSigner from an algosdk Account
 *
 * @param account - The algosdk account to use for signing
 * @param config - Optional configuration for Algod clients
 * @returns A FacilitatorAvmSigner instance
 *
 * @example
 * ```typescript
 * import algosdk from "algosdk";
 * import { toFacilitatorAvmSigner } from "@x402/avm";
 *
 * const account = algosdk.mnemonicToSecretKey("your mnemonic...");
 * const signer = toFacilitatorAvmSigner(account, {
 *   mainnet: new algosdk.Algodv2("", "https://mainnet-api.algonode.cloud", ""),
 *   testnet: new algosdk.Algodv2("", "https://testnet-api.algonode.cloud", ""),
 * });
 * ```
 */
export function toFacilitatorAvmSigner(
  account: algosdk.Account,
  config?: FacilitatorAvmSignerConfig,
): FacilitatorAvmSigner {
  const mainnetClient =
    config?.mainnet ?? new algosdk.Algodv2("", DEFAULT_ALGOD_MAINNET, "");
  const testnetClient =
    config?.testnet ?? new algosdk.Algodv2("", DEFAULT_ALGOD_TESTNET, "");

  const getAlgodForNetwork = (network: Network): algosdk.Algodv2 => {
    const networkStr = network as string;
    if (
      networkStr === ALGORAND_MAINNET_CAIP2 ||
      networkStr === V1_ALGORAND_MAINNET
    ) {
      return mainnetClient;
    }
    if (
      networkStr === ALGORAND_TESTNET_CAIP2 ||
      networkStr === V1_ALGORAND_TESTNET
    ) {
      return testnetClient;
    }
    // Default to testnet for unknown networks
    return testnetClient;
  };

  return {
    getAddresses: () => [account.addr.toString()],

    signTransaction: async (txn: Uint8Array, senderAddress: string) => {
      // Decode the transaction to verify sender
      const decodedTxn = algosdk.decodeUnsignedTransaction(txn);
      const txnSender = algosdk.encodeAddress(decodedTxn.sender.publicKey);

      if (txnSender !== senderAddress) {
        throw new Error(
          `Transaction sender ${txnSender} does not match expected ${senderAddress}`,
        );
      }

      if (txnSender !== account.addr.toString()) {
        throw new Error(
          `Cannot sign transaction for ${txnSender}, signer address is ${account.addr.toString()}`,
        );
      }

      // Sign the transaction
      const signedTxn = algosdk.signTransaction(decodedTxn, account.sk);
      return signedTxn.blob;
    },

    getAlgodClient: (network: Network) => getAlgodForNetwork(network),

    simulateTransactions: async (txns: Uint8Array[], network: Network) => {
      const algod = getAlgodForNetwork(network);

      // Create simulate request
      const request = new algosdk.modelsv2.SimulateRequest({
        txnGroups: [
          new algosdk.modelsv2.SimulateRequestTransactionGroup({
            txns: txns.map(t => algosdk.decodeSignedTransaction(t)),
          }),
        ],
        allowEmptySignatures: true,
        allowUnnamedResources: true,
      });

      return await algod.simulateTransactions(request).do();
    },

    sendTransactions: async (signedTxns: Uint8Array[], network: Network) => {
      const algod = getAlgodForNetwork(network);

      // Combine transactions for atomic group submission
      const combined = new Uint8Array(
        signedTxns.reduce((acc, txn) => acc + txn.length, 0),
      );
      let offset = 0;
      for (const txn of signedTxns) {
        combined.set(txn, offset);
        offset += txn.length;
      }

      const response = await algod.sendRawTransaction(combined).do();
      return response.txid;
    },

    waitForConfirmation: async (
      txId: string,
      network: Network,
      waitRounds = 4,
    ) => {
      const algod = getAlgodForNetwork(network);
      return await algosdk.waitForConfirmation(algod, txId, waitRounds);
    },
  };
}

/**
 * Creates a FacilitatorAvmSigner from multiple accounts for load balancing
 *
 * @param accounts - Array of algosdk accounts
 * @param config - Optional configuration for Algod clients
 * @returns A FacilitatorAvmSigner instance with multiple addresses
 */
export function toMultiAccountFacilitatorAvmSigner(
  accounts: algosdk.Account[],
  config?: FacilitatorAvmSignerConfig,
): FacilitatorAvmSigner {
  if (accounts.length === 0) {
    throw new Error("At least one account is required");
  }

  const mainnetClient =
    config?.mainnet ?? new algosdk.Algodv2("", DEFAULT_ALGOD_MAINNET, "");
  const testnetClient =
    config?.testnet ?? new algosdk.Algodv2("", DEFAULT_ALGOD_TESTNET, "");

  const accountMap = new Map<string, algosdk.Account>();
  for (const account of accounts) {
    accountMap.set(account.addr.toString(), account);
  }

  const getAlgodForNetwork = (network: Network): algosdk.Algodv2 => {
    const networkStr = network as string;
    if (
      networkStr === ALGORAND_MAINNET_CAIP2 ||
      networkStr === V1_ALGORAND_MAINNET
    ) {
      return mainnetClient;
    }
    if (
      networkStr === ALGORAND_TESTNET_CAIP2 ||
      networkStr === V1_ALGORAND_TESTNET
    ) {
      return testnetClient;
    }
    return testnetClient;
  };

  return {
    getAddresses: () => accounts.map(a => a.addr.toString()),

    signTransaction: async (txn: Uint8Array, senderAddress: string) => {
      const account = accountMap.get(senderAddress);
      if (!account) {
        throw new Error(
          `No signing key for address ${senderAddress}. Available: ${[...accountMap.keys()].join(", ")}`,
        );
      }

      const decodedTxn = algosdk.decodeUnsignedTransaction(txn);
      const txnSender = algosdk.encodeAddress(decodedTxn.sender.publicKey);

      if (txnSender !== senderAddress) {
        throw new Error(
          `Transaction sender ${txnSender} does not match expected ${senderAddress}`,
        );
      }

      const signedTxn = algosdk.signTransaction(decodedTxn, account.sk);
      return signedTxn.blob;
    },

    getAlgodClient: (network: Network) => getAlgodForNetwork(network),

    simulateTransactions: async (txns: Uint8Array[], network: Network) => {
      const algod = getAlgodForNetwork(network);
      const request = new algosdk.modelsv2.SimulateRequest({
        txnGroups: [
          new algosdk.modelsv2.SimulateRequestTransactionGroup({
            txns: txns.map(t => algosdk.decodeSignedTransaction(t)),
          }),
        ],
        allowEmptySignatures: true,
        allowUnnamedResources: true,
      });
      return await algod.simulateTransactions(request).do();
    },

    sendTransactions: async (signedTxns: Uint8Array[], network: Network) => {
      const algod = getAlgodForNetwork(network);
      const combined = new Uint8Array(
        signedTxns.reduce((acc, txn) => acc + txn.length, 0),
      );
      let offset = 0;
      for (const txn of signedTxns) {
        combined.set(txn, offset);
        offset += txn.length;
      }
      const response = await algod.sendRawTransaction(combined).do();
      return response.txid;
    },

    waitForConfirmation: async (
      txId: string,
      network: Network,
      waitRounds = 4,
    ) => {
      const algod = getAlgodForNetwork(network);
      return await algosdk.waitForConfirmation(algod, txId, waitRounds);
    },
  };
}

/**
 * Type guard to check if a wallet implements ClientAvmSigner
 *
 * @param wallet - The wallet to check
 * @returns True if the wallet implements ClientAvmSigner
 */
export function isAvmSignerWallet(wallet: unknown): wallet is ClientAvmSigner {
  return (
    typeof wallet === "object" &&
    wallet !== null &&
    "address" in wallet &&
    typeof (wallet as ClientAvmSigner).address === "string" &&
    "signTransactions" in wallet &&
    typeof (wallet as ClientAvmSigner).signTransactions === "function"
  );
}

/**
 * Converts an algosdk Account to a ClientAvmSigner for local signing
 *
 * @param account - The algosdk account
 * @returns A ClientAvmSigner instance
 */
export function toClientAvmSigner(account: algosdk.Account): ClientAvmSigner {
  return {
    address: account.addr.toString(),
    signTransactions: async (
      txns: Uint8Array[],
      indexesToSign?: number[],
    ): Promise<(Uint8Array | null)[]> => {
      const signedTxns: (Uint8Array | null)[] = [];
      const indexes = indexesToSign ?? txns.map((_, i) => i);

      for (let i = 0; i < txns.length; i++) {
        if (indexes.includes(i)) {
          const decodedTxn = algosdk.decodeUnsignedTransaction(txns[i]);
          const signedTxn = algosdk.signTransaction(decodedTxn, account.sk);
          signedTxns.push(signedTxn.blob);
        } else {
          signedTxns.push(null);
        }
      }

      return signedTxns;
    },
  };
}
