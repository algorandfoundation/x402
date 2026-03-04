/**
 * AVM (Algorand) Signer Interfaces for x402 Payment Protocol
 *
 * This module defines the signer interfaces for client and facilitator operations.
 * Use the provided helper functions for the common case, or implement the interfaces
 * directly for custom signing (e.g., KMS, hardware wallets, multi-sig).
 *
 * @example Client signer using helper:
 * ```typescript
 * import { toClientAvmSigner } from "@x402/avm";
 *
 * const signer = toClientAvmSigner(process.env.AVM_PRIVATE_KEY!);
 * ```
 *
 * @example Facilitator signer using helper:
 * ```typescript
 * import { toFacilitatorAvmSigner } from "@x402/avm";
 *
 * const signer = toFacilitatorAvmSigner(process.env.AVM_PRIVATE_KEY!);
 * ```
 */

import algosdk from 'algosdk'
import type { Network } from '@x402/core/types'
import {
  ALGORAND_TESTNET_CAIP2,
  DEFAULT_ALGOD_MAINNET,
  DEFAULT_ALGOD_TESTNET,
  V1_ALGORAND_TESTNET,
} from './constants'

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
   * Should be an algosdk.Algodv2 instance
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
 * @example Using the helper function:
 * ```typescript
 * import { toFacilitatorAvmSigner } from "@x402/avm";
 *
 * const signer = toFacilitatorAvmSigner(process.env.AVM_PRIVATE_KEY!);
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
   * @returns Algod client instance (algosdk.Algodv2)
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

/**
 * Decode a Base64-encoded 64-byte private key into address and secret key
 */
function decodePrivateKey(privateKeyBase64: string): { address: string; secretKey: Buffer } {
  const secretKey = Buffer.from(privateKeyBase64, 'base64')
  if (secretKey.length !== 64) {
    throw new Error(
      'AVM private key must be a Base64-encoded 64-byte key (32-byte seed + 32-byte public key)',
    )
  }
  const address = algosdk.encodeAddress(secretKey.slice(32))
  return { address, secretKey }
}

/**
 * Check if a network identifier refers to testnet
 */
function isTestnet(network: string): boolean {
  return (
    network === ALGORAND_TESTNET_CAIP2 ||
    network === V1_ALGORAND_TESTNET ||
    network.toLowerCase().includes('testnet')
  )
}

/**
 * Create a ClientAvmSigner from a Base64-encoded 64-byte private key.
 *
 * This is a convenience helper for the common case of signing with a raw private key.
 * For custom signing (KMS, hardware wallets, multi-sig), implement {@link ClientAvmSigner} directly.
 *
 * @param privateKeyBase64 - Base64-encoded 64-byte key (32-byte seed + 32-byte public key)
 * @returns A configured ClientAvmSigner
 *
 * @example
 * ```typescript
 * import { toClientAvmSigner } from "@x402/avm";
 * import { ExactAvmScheme } from "@x402/avm/exact/client";
 *
 * const signer = toClientAvmSigner(process.env.AVM_PRIVATE_KEY!);
 * client.register("algorand:*", new ExactAvmScheme(signer));
 * ```
 */
export function toClientAvmSigner(privateKeyBase64: string): ClientAvmSigner {
  const { address, secretKey } = decodePrivateKey(privateKeyBase64)
  return {
    address,
    signTransactions: async (txns: Uint8Array[], indexesToSign?: number[]) => {
      return txns.map((txn, i) => {
        if (indexesToSign && !indexesToSign.includes(i)) return null
        const decoded = algosdk.decodeUnsignedTransaction(txn)
        const signed = algosdk.signTransaction(decoded, secretKey)
        return signed.blob
      })
    },
  }
}

/**
 * Create a FacilitatorAvmSigner from a Base64-encoded 64-byte private key.
 *
 * This is a convenience helper for the common case of facilitating with a raw private key.
 * For custom signing (KMS, hardware wallets, multi-sig), implement {@link FacilitatorAvmSigner} directly.
 *
 * Creates Algod clients using AlgoNode public endpoints by default, with optional URL overrides
 * via config. Caches Algod client instances per network type (testnet/mainnet).
 *
 * @param privateKeyBase64 - Base64-encoded 64-byte key (32-byte seed + 32-byte public key)
 * @param config - Optional configuration for Algod client URLs and token
 * @returns A configured FacilitatorAvmSigner
 *
 * @example
 * ```typescript
 * import { toFacilitatorAvmSigner } from "@x402/avm";
 * import { ExactAvmScheme } from "@x402/avm/exact/facilitator";
 *
 * const signer = toFacilitatorAvmSigner(process.env.AVM_PRIVATE_KEY!);
 * facilitator.register("algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=", new ExactAvmScheme(signer));
 * ```
 */
export function toFacilitatorAvmSigner(
  privateKeyBase64: string,
  config?: FacilitatorAvmSignerConfig,
): FacilitatorAvmSigner {
  const { address, secretKey } = decodePrivateKey(privateKeyBase64)

  // Cache Algod clients per network type
  const clientCache = new Map<string, algosdk.Algodv2>()

  function getAlgodForNetwork(network: string): algosdk.Algodv2 {
    const key = isTestnet(network) ? 'testnet' : 'mainnet'
    let client = clientCache.get(key)
    if (!client) {
      const token = config?.algodToken ?? ''
      if (isTestnet(network)) {
        const url = config?.testnetUrl ?? DEFAULT_ALGOD_TESTNET
        client = new algosdk.Algodv2(token, url, '')
      } else {
        const url = config?.mainnetUrl ?? DEFAULT_ALGOD_MAINNET
        client = new algosdk.Algodv2(token, url, '')
      }
      clientCache.set(key, client)
    }
    return client
  }

  return {
    getAddresses: () => [address] as readonly string[],

    signTransaction: async (txn: Uint8Array, _senderAddress: string) => {
      const decoded = algosdk.decodeUnsignedTransaction(txn)
      const signed = algosdk.signTransaction(decoded, secretKey)
      return signed.blob
    },

    getAlgodClient: (network: string) => getAlgodForNetwork(network),

    simulateTransactions: async (txns: Uint8Array[], network: string) => {
      const algodClient = getAlgodForNetwork(network)
      const request = new algosdk.modelsv2.SimulateRequest({
        txnGroups: [
          new algosdk.modelsv2.SimulateRequestTransactionGroup({
            txns: txns.map((txn) => algosdk.decodeSignedTransaction(txn)),
          }),
        ],
        allowUnnamedResources: true,
      })
      return await algodClient.simulateTransactions(request).do()
    },

    sendTransactions: async (signedTxns: Uint8Array[], network: string) => {
      const algodClient = getAlgodForNetwork(network)
      const response = await algodClient.sendRawTransaction(signedTxns).do()
      return response.txid
    },

    waitForConfirmation: async (txId: string, network: string, waitRounds: number = 4) => {
      const algodClient = getAlgodForNetwork(network)
      return await algosdk.waitForConfirmation(algodClient, txId, waitRounds)
    },
  }
}
