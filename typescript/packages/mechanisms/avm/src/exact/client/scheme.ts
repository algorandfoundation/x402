/**
 * AVM Client Scheme for Exact Payment Protocol
 *
 * Creates atomic transaction groups for Algorand ASA transfers.
 */

import algosdk from 'algosdk'
import type {
  PaymentRequirements,
  SchemeNetworkClient,
  PaymentPayloadResult,
} from '@x402/core/types'
import type { ClientAvmSigner, ClientAvmConfig } from '../../signer'
import type { ExactAvmPayloadV2 } from '../../types'
import { createAlgodClient, encodeTransaction } from '../../utils'
import { USDC_CONFIG, DEFAULT_ALGOD_TESTNET } from '../../constants'

/**
 * AVM client implementation for the Exact payment scheme.
 *
 * Creates atomic transaction groups with ASA transfers for x402 payments.
 * Supports optional fee payer transactions for gasless payments.
 */
export class ExactAvmScheme implements SchemeNetworkClient {
  readonly scheme = 'exact'

  /**
   * Creates a new ExactAvmScheme instance.
   *
   * @param signer - The AVM signer for client operations
   * @param config - Optional configuration for Algod client
   */
  constructor(
    private readonly signer: ClientAvmSigner,
    private readonly config?: ClientAvmConfig,
  ) {}

  /**
   * Creates a payment payload for the Exact scheme.
   *
   * Constructs an atomic transaction group with:
   * - Optional fee payer transaction (if feePayer specified in requirements.extra)
   * - ASA transfer transaction to payTo address
   *
   * @param x402Version - The x402 protocol version
   * @param paymentRequirements - The payment requirements
   * @returns Promise resolving to a payment payload result
   */
  async createPaymentPayload(
    x402Version: number,
    paymentRequirements: PaymentRequirements,
  ): Promise<PaymentPayloadResult> {
    const { amount, asset, payTo, network, extra } = paymentRequirements

    // Get Algod client
    const algodClient = (this.config?.algodClient ??
      createAlgodClient(
        network,
        this.config?.algodUrl ?? DEFAULT_ALGOD_TESTNET,
        this.config?.algodToken,
      )) as algosdk.Algodv2

    // Get suggested params
    const suggestedParams = await algodClient.getTransactionParams().do()

    // Get asset ID (from requirements or default USDC)
    const assetId = this.getAssetId(asset, network)

    // Get fee payer address from extra if provided
    const feePayer = extra?.feePayer as string | undefined

    const transactions: algosdk.Transaction[] = []
    let paymentIndex = 0

    // Calculate total transaction count for fee pooling
    // When fee payer exists: 1 fee payer txn + 1 ASA transfer txn = 2
    const totalTxnCount = feePayer ? 2 : 1
    const minFee = suggestedParams.minFee ?? BigInt(1000)

    // Build fee payer transaction if specified
    // Fee payer pays for all transactions in the group (pooled fees)
    if (feePayer) {
      // Create params with pooled fee (minFee * number of transactions)
      const feePayerParams = {
        ...suggestedParams,
        fee: minFee * BigInt(totalTxnCount),
        flatFee: true,
      }

      const feePayerTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
        sender: algosdk.Address.fromString(feePayer),
        receiver: algosdk.Address.fromString(feePayer), // Self-payment
        amount: 0,
        suggestedParams: feePayerParams,
        note: new Uint8Array(Buffer.from(`x402-fee-payer-${Date.now()}`)),
      })
      transactions.push(feePayerTxn)
      paymentIndex = 1 // Payment will be second transaction
    }

    // Build ASA transfer transaction
    // When fee payer exists, set fee to 0 (fee payer covers all fees)
    const assetTransferParams = feePayer
      ? { ...suggestedParams, fee: BigInt(0), flatFee: true }
      : suggestedParams

    const assetTransferTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
      sender: algosdk.Address.fromString(this.signer.address),
      receiver: algosdk.Address.fromString(payTo),
      amount: BigInt(amount),
      assetIndex: Number(assetId),
      suggestedParams: assetTransferParams,
      note: new Uint8Array(Buffer.from(`x402-payment-v${x402Version}-${Date.now()}`)),
    })
    transactions.push(assetTransferTxn)

    // Assign group ID if multiple transactions
    if (transactions.length > 1) {
      algosdk.assignGroupID(transactions)
    }

    // Encode transactions
    const encodedTxns = transactions.map(txn => txn.toByte())

    // Determine which transactions the client should sign
    // Client signs all except fee payer transactions
    const clientIndexes = transactions
      .map((txn, i) => {
        const sender = algosdk.encodeAddress(txn.sender.publicKey)
        return sender === this.signer.address ? i : -1
      })
      .filter(i => i !== -1)

    // Log transaction details for debugging
    console.log('[x402 AVM Client] Creating payment:', {
      sender: this.signer.address,
      receiver: payTo,
      amount: amount,
      assetId: this.getAssetId(asset, network),
      network,
      clientIndexes,
      txnCount: transactions.length,
      hasFeePayer: !!feePayer,
    })

    // Sign client's transactions
    const signedTxns = await this.signer.signTransactions(encodedTxns, clientIndexes)

    // Log signing result
    console.log('[x402 AVM Client] Signed transactions:', {
      signedCount: signedTxns.filter(t => t !== null).length,
      totalCount: signedTxns.length,
      signedIndexes: signedTxns.map((t, i) => (t !== null ? i : -1)).filter(i => i !== -1),
    })

    // Build payment group with signed/unsigned transactions
    const paymentGroup: string[] = encodedTxns.map((txnBytes, i) => {
      const signedTxn = signedTxns[i]
      if (signedTxn) {
        return encodeTransaction(signedTxn)
      }
      // Return unsigned transaction for facilitator to sign
      return encodeTransaction(txnBytes)
    })

    const payload: ExactAvmPayloadV2 = {
      paymentGroup,
      paymentIndex,
    }

    return {
      x402Version,
      payload: payload as unknown as Record<string, unknown>,
    }
  }

  /**
   * Gets the asset ID from the requirements or defaults to USDC
   *
   * @param asset - Asset identifier from requirements
   * @param network - Network identifier
   * @returns Asset ID as string
   */
  private getAssetId(asset: string, network: string): string {
    // If asset is already a numeric string, use it directly
    if (/^\d+$/.test(asset)) {
      return asset
    }

    // Try to get from USDC config
    const usdcConfig = USDC_CONFIG[network]
    if (usdcConfig) {
      return usdcConfig.asaId
    }

    // Default to the asset as-is (might be an ASA ID)
    return asset
  }
}
