/**
 * AVM (Algorand) Signer Interfaces for x402 Payment Protocol
 *
 * This module defines the signer interfaces for client and facilitator operations.
 * Implementations should be provided by the integrator using @algorandfoundation/algokit-utils.
 *
 * @example Client implementation with algokit-utils:
 * ```typescript
 * import { ed25519Generator } from "@algorandfoundation/algokit-utils/crypto";
 * import { encodeAddress } from "@algorandfoundation/algokit-utils/common";
 * import { decodeTransaction, encodeTransactionRaw } from "@algorandfoundation/algokit-utils/transact";
 * import type { ClientAvmSigner } from "@x402/avm";
 *
 * const secretKey = Buffer.from(process.env.AVM_PRIVATE_KEY!, 'base64');
 * const seed = secretKey.slice(0, 32);
 * const { ed25519Pubkey, rawEd25519Signer } = ed25519Generator(seed);
 * const address = encodeAddress(ed25519Pubkey);
 *
 * const signer: ClientAvmSigner = {
 *   address,
 *   signTransactions: async (txns, indexesToSign) => {
 *     return Promise.all(txns.map(async (txn, i) => {
 *       if (indexesToSign && !indexesToSign.includes(i)) return null;
 *       const decoded = decodeTransaction(txn);
 *       const sig = await rawEd25519Signer(encodeTransactionRaw(decoded));
 *       return encodeTransactionRaw({ ...decoded, sig } as any);
 *     }));
 *   },
 * };
 * ```
 */

import type { Network } from '@x402/core/types'

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
  address: string

  /**
   * Sign one or more transactions
   *
   * @param txns - Array of unsigned transactions (encoded as Uint8Array)
   * @param indexesToSign - Optional array of indexes to sign (if not provided, sign all)
   * @returns Promise resolving to array of signed transactions (null for unsigned)
   */
  signTransactions(txns: Uint8Array[], indexesToSign?: number[]): Promise<(Uint8Array | null)[]>
}

/**
 * Configuration for client AVM operations
 */
export interface ClientAvmConfig {
  /**
   * Pre-configured Algod client (takes precedence over URL)
   * Should be an AlgodClient instance from @algorandfoundation/algokit-utils
   */
  algodClient?: unknown

  /**
   * Algod API URL (used if algodClient not provided)
   */
  algodUrl?: string

  /**
   * Algod API token
   */
  algodToken?: string
}

/**
 * Facilitator signer interface for Algorand operations
 *
 * Used by the facilitator to verify and settle payments.
 * Supports multiple addresses for load balancing and key rotation.
 *
 * @example Implementation with algokit-utils:
 * ```typescript
 * import { ed25519Generator } from "@algorandfoundation/algokit-utils/crypto";
 * import { encodeAddress } from "@algorandfoundation/algokit-utils/common";
 * import { AlgodClient } from "@algorandfoundation/algokit-utils/algod-client";
 * import type { FacilitatorAvmSigner } from "@x402/avm";
 *
 * const secretKey = Buffer.from(process.env.AVM_PRIVATE_KEY!, 'base64');
 * const seed = secretKey.slice(0, 32);
 * const { ed25519Pubkey, rawEd25519Signer } = ed25519Generator(seed);
 * const address = encodeAddress(ed25519Pubkey);
 * const algodClient = new AlgodClient({ baseUrl: "https://testnet-api.algonode.cloud" });
 *
 * const signer: FacilitatorAvmSigner = {
 *   getAddresses: () => [address],
 *   signTransaction: async (txn, senderAddress) => {
 *     const decoded = decodeTransaction(txn);
 *     const sig = await rawEd25519Signer(encodeTransactionRaw(decoded));
 *     return encodeSignedTransaction({ txn: decoded, sig });
 *   },
 *   getAlgodClient: (network) => algodClient,
 *   simulateTransactions: async (txns, network) => { ... },
 *   sendTransactions: async (signedTxns, network) => { ... },
 *   waitForConfirmation: async (txId, network, waitRounds) => { ... },
 * };
 * ```
 */
export interface FacilitatorAvmSigner {
  /**
   * Get all addresses this facilitator can use as fee payers
   *
   * @returns Array of Algorand addresses
   */
  getAddresses(): readonly string[]

  /**
   * Sign a transaction with the signer matching the sender address
   *
   * @param txn - Transaction bytes to sign
   * @param senderAddress - Expected sender address (for verification)
   * @returns Promise resolving to signed transaction bytes
   */
  signTransaction(txn: Uint8Array, senderAddress: string): Promise<Uint8Array>

  /**
   * Get Algod client for a specific network
   *
   * @param network - Network identifier (CAIP-2 or V1 format)
   * @returns Algod client instance (AlgodClient from @algorandfoundation/algokit-utils)
   */
  getAlgodClient(network: Network): unknown

  /**
   * Simulate a transaction group before submission
   *
   * @param txns - Array of signed transaction bytes
   * @param network - Network identifier
   * @returns Promise resolving to simulation response
   */
  simulateTransactions(txns: Uint8Array[], network: Network): Promise<unknown>

  /**
   * Submit signed transactions to the network
   *
   * @param signedTxns - Array of signed transaction bytes
   * @param network - Network identifier
   * @returns Promise resolving to transaction ID
   */
  sendTransactions(signedTxns: Uint8Array[], network: Network): Promise<string>

  /**
   * Wait for a transaction to be confirmed
   *
   * @param txId - Transaction ID
   * @param network - Network identifier
   * @param waitRounds - Number of rounds to wait (default: 4)
   * @returns Promise resolving to pending transaction info
   */
  waitForConfirmation(txId: string, network: Network, waitRounds?: number): Promise<unknown>
}

/**
 * Configuration for creating a facilitator signer
 */
export interface FacilitatorAvmSignerConfig {
  /**
   * Algod URL for mainnet
   */
  mainnetUrl?: string

  /**
   * Algod URL for testnet
   */
  testnetUrl?: string

  /**
   * Algod API token
   */
  algodToken?: string
}

/**
 * Type guard to check if a wallet implements ClientAvmSigner
 *
 * @param wallet - The wallet to check
 * @returns True if the wallet implements ClientAvmSigner
 */
export function isAvmSignerWallet(wallet: unknown): wallet is ClientAvmSigner {
  return (
    typeof wallet === 'object' &&
    wallet !== null &&
    'address' in wallet &&
    typeof (wallet as ClientAvmSigner).address === 'string' &&
    'signTransactions' in wallet &&
    typeof (wallet as ClientAvmSigner).signTransactions === 'function'
  )
}
