/**
 * AVM Facilitator Scheme for Exact Payment Protocol
 *
 * Verifies and settles Algorand ASA transfer payments.
 */

import algosdk from "algosdk";
import type {
  Network,
  PaymentPayload,
  PaymentRequirements,
  SchemeNetworkFacilitator,
  SettleResponse,
  VerifyResponse,
} from "@x402/core/types";
import type { FacilitatorAvmSigner } from "../../signer";
import type { ExactAvmPayloadV2 } from "../../types";
import { isExactAvmPayload } from "../../types";
import {
  decodeTransaction,
  hasSignature,
} from "../../utils";
import { MAX_ATOMIC_GROUP_SIZE, MAX_REASONABLE_FEE } from "../../constants";

/**
 * Verification error reasons
 */
export const VerifyErrorReason = {
  INVALID_PAYLOAD_FORMAT: "Invalid payload format",
  GROUP_SIZE_EXCEEDED: "Transaction group exceeds maximum size",
  INVALID_PAYMENT_INDEX: "Payment index out of bounds",
  INVALID_TRANSACTION: "Invalid transaction encoding",
  INVALID_GROUP_ID: "Transactions have inconsistent group IDs",
  PAYMENT_NOT_ASSET_TRANSFER: "Payment transaction is not an asset transfer",
  AMOUNT_MISMATCH: "Payment amount does not match requirements",
  RECEIVER_MISMATCH: "Payment receiver does not match payTo address",
  ASSET_MISMATCH: "Payment asset does not match requirements",
  INVALID_FEE_PAYER: "Fee payer transaction has invalid parameters",
  FEE_TOO_HIGH: "Fee payer transaction fee exceeds maximum",
  PAYMENT_NOT_SIGNED: "Payment transaction is not signed",
  SIMULATION_FAILED: "Transaction simulation failed",
  // Security error reasons
  UNSIGNED_NON_FACILITATOR_TXN: "Unsigned transaction from non-facilitator address",
  SECURITY_REKEY_NOT_ALLOWED: "Rekey transactions are not allowed",
  SECURITY_CLOSE_TO_NOT_ALLOWED: "Close-to transactions are not allowed",
  SECURITY_KEYREG_NOT_ALLOWED: "Key registration transactions are not allowed",
} as const;

/**
 * AVM facilitator implementation for the Exact payment scheme.
 *
 * Verifies atomic transaction groups and settles ASA transfers for x402 payments.
 * Supports gasless transactions by signing fee payer transactions.
 */
export class ExactAvmScheme implements SchemeNetworkFacilitator {
  readonly scheme = "exact";
  readonly caipFamily = "algorand:*";

  /**
   * Creates a new ExactAvmScheme facilitator instance.
   *
   * @param signer - The AVM signer for facilitator operations
   */
  constructor(private readonly signer: FacilitatorAvmSigner) {}

  /**
   * Get mechanism-specific extra data for the supported kinds endpoint.
   * For AVM, returns the feePayer address for gasless transactions.
   *
   * @param _ - The network identifier (unused, feePayer is network-agnostic)
   * @returns Extra data with feePayer address
   */
  getExtra(_: string): Record<string, unknown> | undefined {
    const addresses = this.signer.getAddresses();
    if (addresses.length === 0) {
      return undefined;
    }

    // Random selection for load balancing
    const randomIndex = Math.floor(Math.random() * addresses.length);
    return { feePayer: addresses[randomIndex] };
  }

  /**
   * Get signer addresses used by this facilitator.
   * Returns all addresses this facilitator can use for signing fee payer transactions.
   *
   * @param _ - The network identifier (unused, addresses are network-agnostic)
   * @returns Array of facilitator wallet addresses
   */
  getSigners(_: string): string[] {
    return [...this.signer.getAddresses()];
  }

  /**
   * Verifies a payment payload.
   *
   * Verification steps:
   * 1. Validate payload format and structure
   * 2. Decode and validate transaction group
   * 3. Apply security constraints
   * 4. Verify payment transaction (amount, receiver, asset)
   * 5. Prepare signed group (verify + sign fee payers)
   * 6. Simulate transaction group
   *
   * @param payload - The payment payload to verify
   * @param requirements - The payment requirements
   * @returns Promise resolving to verification response
   */
  async verify(
    payload: PaymentPayload,
    requirements: PaymentRequirements,
  ): Promise<VerifyResponse> {
    const rawPayload = payload.payload as unknown;

    if (!isExactAvmPayload(rawPayload)) {
      return { isValid: false, invalidReason: VerifyErrorReason.INVALID_PAYLOAD_FORMAT };
    }

    const { paymentGroup, paymentIndex } = rawPayload as ExactAvmPayloadV2;

    if (paymentGroup.length > MAX_ATOMIC_GROUP_SIZE) {
      return { isValid: false, invalidReason: VerifyErrorReason.GROUP_SIZE_EXCEEDED };
    }
    if (paymentIndex < 0 || paymentIndex >= paymentGroup.length) {
      return { isValid: false, invalidReason: VerifyErrorReason.INVALID_PAYMENT_INDEX };
    }

    const facilitatorAddresses = this.signer.getAddresses();

    // Decode all transactions and validate group structure
    const decoded = this.decodeTransactionGroup(paymentGroup, facilitatorAddresses);
    if ("error" in decoded) return decoded.error;

    // Security constraints on all transactions
    const securityCheck = this.verifySecurityConstraints(decoded.txns);
    if (!securityCheck.isValid) return securityCheck;

    // Payment transaction correctness
    const paymentCheck = this.verifyPaymentTransaction(
      decoded.txns[paymentIndex], requirements, paymentGroup[paymentIndex],
    );
    if (!paymentCheck.isValid) return paymentCheck;

    // Verify fee payers and sign them for simulation
    const prepared = await this.prepareSignedGroup(decoded.txns, paymentGroup);
    if ("error" in prepared) return prepared.error;

    // Simulate the assembled group
    return this.simulateTransactionGroup(prepared.signedTxns, requirements.network);
  }

  /**
   * Decodes all transactions in the group and validates structure.
   *
   * - Signed transactions are decoded as-is
   * - Unsigned transactions are only accepted from facilitator addresses (fee payers)
   * - Verifies group ID consistency across all transactions
   */
  private decodeTransactionGroup(
    paymentGroup: string[],
    facilitatorAddresses: readonly string[],
  ): { txns: algosdk.SignedTransaction[] } | { error: VerifyResponse } {
    const txns: algosdk.SignedTransaction[] = [];

    for (let i = 0; i < paymentGroup.length; i++) {
      try {
        const bytes = decodeTransaction(paymentGroup[i]);

        try {
          txns.push(algosdk.decodeSignedTransaction(bytes));
        } catch {
          // Unsigned transaction — only the facilitator's fee payer txn should be unsigned
          const unsignedTxn = algosdk.decodeUnsignedTransaction(bytes);
          const sender = algosdk.encodeAddress(unsignedTxn.sender.publicKey);

          if (!facilitatorAddresses.includes(sender)) {
            return {
              error: {
                isValid: false,
                invalidReason: `${VerifyErrorReason.UNSIGNED_NON_FACILITATOR_TXN}: transaction at index ${i} from ${sender}`,
              },
            };
          }

          const encodedForSimulate = algosdk.encodeUnsignedSimulateTransaction(unsignedTxn);
          txns.push(algosdk.decodeSignedTransaction(encodedForSimulate));
        }
      } catch {
        return {
          error: {
            isValid: false,
            invalidReason: `${VerifyErrorReason.INVALID_TRANSACTION}: Failed to decode transaction at index ${i}`,
          },
        };
      }
    }

    // Verify group ID consistency
    if (txns.length > 1) {
      const firstGroup = txns[0].txn.group;
      const firstGroupId = firstGroup
        ? Buffer.from(firstGroup).toString("base64")
        : null;

      for (let i = 1; i < txns.length; i++) {
        const group = txns[i].txn.group;
        const groupId = group
          ? Buffer.from(group).toString("base64")
          : null;
        if (groupId !== firstGroupId) {
          return {
            error: { isValid: false, invalidReason: VerifyErrorReason.INVALID_GROUP_ID },
          };
        }
      }
    }

    return { txns };
  }

  /**
   * Verifies fee payer transactions and signs them, returning the assembled group
   * ready for simulation or submission.
   */
  private async prepareSignedGroup(
    decodedTxns: algosdk.SignedTransaction[],
    paymentGroup: string[],
  ): Promise<{ signedTxns: Uint8Array[] } | { error: VerifyResponse }> {
    const facilitatorAddresses = this.signer.getAddresses();
    const signedTxns: Uint8Array[] = [];

    for (let i = 0; i < decodedTxns.length; i++) {
      const txn = decodedTxns[i].txn;
      const sender = algosdk.encodeAddress(txn.sender.publicKey);

      if (facilitatorAddresses.includes(sender)) {
        const feeCheck = this.verifyFeePayerTransaction(txn);
        if (!feeCheck.isValid) return { error: feeCheck };

        try {
          const signedTxn = await this.signer.signTransaction(txn.toByte(), sender);
          signedTxns.push(signedTxn);
        } catch (error) {
          return {
            error: {
              isValid: false,
              invalidReason: `Failed to sign fee payer transaction: ${error instanceof Error ? error.message : "Unknown error"}`,
            },
          };
        }
      } else {
        signedTxns.push(decodeTransaction(paymentGroup[i]));
      }
    }

    return { signedTxns };
  }

  /**
   * Simulates the transaction group and returns the verification result.
   */
  private async simulateTransactionGroup(
    signedTxns: Uint8Array[],
    network: Network,
  ): Promise<VerifyResponse> {
    try {
      const simResult = await this.signer.simulateTransactions(
        signedTxns, network,
      ) as { txnGroups?: Array<{ failureMessage?: string }> };

      if (simResult.txnGroups?.[0]?.failureMessage) {
        return {
          isValid: false,
          invalidReason: `${VerifyErrorReason.SIMULATION_FAILED}: ${simResult.txnGroups[0].failureMessage}`,
        };
      }

      return { isValid: true };
    } catch (error) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.SIMULATION_FAILED}: ${error instanceof Error ? error.message : "Unknown error"}`,
      };
    }
  }

  /**
   * Settles a payment by submitting the transaction group.
   *
   * Settlement steps:
   * 1. Verify the payment first
   * 2. Sign fee payer transactions
   * 3. Submit transaction group
   * 4. Return transaction ID
   *
   * Note: Algorand has instant finality, so no confirmation wait is needed.
   *
   * @param payload - The payment payload to settle
   * @param requirements - The payment requirements
   * @returns Promise resolving to settlement response
   */
  async settle(
    payload: PaymentPayload,
    requirements: PaymentRequirements,
  ): Promise<SettleResponse> {
    // First verify the payment
    const verification = await this.verify(payload, requirements);
    if (!verification.isValid) {
      return {
        success: false,
        errorReason: verification.invalidReason,
        transaction: "",
        network: requirements.network,
      };
    }

    const avmPayload = payload.payload as unknown as ExactAvmPayloadV2;
    const { paymentGroup, paymentIndex } = avmPayload;

    // Decode and sign transactions (handles both signed and unsigned for fee abstraction)
    const facilitatorAddresses = this.signer.getAddresses();
    const signedTxns: Uint8Array[] = [];

    for (let i = 0; i < paymentGroup.length; i++) {
      const txnBytes = decodeTransaction(paymentGroup[i]);

      // Try to decode as signed, fall back to unsigned for fee payer transactions
      let txn: algosdk.Transaction;
      let isAlreadySigned = false;
      try {
        const stxn = algosdk.decodeSignedTransaction(txnBytes);
        txn = stxn.txn;
        isAlreadySigned = stxn.sig !== undefined || stxn.lsig !== undefined || stxn.msig !== undefined;
      } catch {
        txn = algosdk.decodeUnsignedTransaction(txnBytes);
        isAlreadySigned = false;
      }

      const sender = algosdk.encodeAddress(txn.sender.publicKey);

      if (facilitatorAddresses.includes(sender)) {
        // Sign fee payer transaction
        const unsignedTxn = txn.toByte();
        const signedTxn = await this.signer.signTransaction(unsignedTxn, sender);
        signedTxns.push(signedTxn);
      } else if (isAlreadySigned) {
        // Use the already-signed transaction
        signedTxns.push(txnBytes);
      } else {
        // Transaction needs signing but we're not the sender - this shouldn't happen
        return {
          success: false,
          errorReason: `Transaction at index ${i} is unsigned but sender ${sender} is not a facilitator address`,
          transaction: "",
          network: requirements.network,
        };
      }
    }

    // Submit transaction group
    try {
      await this.signer.sendTransactions(signedTxns, requirements.network);

      // Get the payment transaction ID
      const paymentTxnBytes = signedTxns[paymentIndex];
      const paymentStxn = algosdk.decodeSignedTransaction(paymentTxnBytes);
      const paymentTxId = paymentStxn.txn.txID();

      return {
        success: true,
        transaction: paymentTxId,
        network: requirements.network,
      };
    } catch (error) {
      return {
        success: false,
        errorReason: `Failed to submit transaction: ${error instanceof Error ? error.message : "Unknown error"}`,
        transaction: "",
        network: requirements.network,
      };
    }
  }

  /**
   * Verifies the payment transaction matches requirements
   */
  private verifyPaymentTransaction(
    stxn: algosdk.SignedTransaction,
    requirements: PaymentRequirements,
    encodedTxn: string,
  ): VerifyResponse {
    const txn = stxn.txn;

    // Must be an asset transfer
    if (txn.type !== "axfer") {
      return {
        isValid: false,
        invalidReason: VerifyErrorReason.PAYMENT_NOT_ASSET_TRANSFER,
      };
    }

    // Access asset transfer properties via assetTransfer (algosdk v3 structure)
    // In v3, asset transfer fields are nested: txn.assetTransfer.{amount, receiver, assetIndex}
    const assetTransfer = (txn as unknown as {
      assetTransfer?: {
        amount?: bigint;
        assetIndex?: bigint;
        receiver?: { publicKey: Uint8Array };
        assetSender?: { publicKey: Uint8Array };
        closeRemainderTo?: { publicKey: Uint8Array };
      }
    }).assetTransfer;

    if (!assetTransfer) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.PAYMENT_NOT_ASSET_TRANSFER}: missing assetTransfer data`,
      };
    }

    const amount = (assetTransfer.amount ?? BigInt(0)).toString();

    if (amount !== requirements.amount) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.AMOUNT_MISMATCH}: expected ${requirements.amount}, got ${amount}`,
      };
    }

    // Verify receiver
    const receiver = assetTransfer.receiver
      ? algosdk.encodeAddress(assetTransfer.receiver.publicKey)
      : "";

    if (receiver !== requirements.payTo) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.RECEIVER_MISMATCH}: expected ${requirements.payTo}, got ${receiver}`,
      };
    }

    // Verify asset
    const assetId = assetTransfer.assetIndex?.toString() ?? "";

    if (assetId !== requirements.asset) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.ASSET_MISMATCH}: expected ${requirements.asset}, got ${assetId}`,
      };
    }

    // Verify signature exists
    const txnBytes = decodeTransaction(encodedTxn);
    if (!hasSignature(txnBytes)) {
      return {
        isValid: false,
        invalidReason: VerifyErrorReason.PAYMENT_NOT_SIGNED,
      };
    }

    return { isValid: true };
  }

  /**
   * Verifies a fee payer transaction is safe to sign
   */
  private verifyFeePayerTransaction(txn: algosdk.Transaction): VerifyResponse {
    // Must be a payment transaction (for fee payment)
    if (txn.type !== "pay") {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.INVALID_FEE_PAYER}: expected payment transaction, got ${txn.type}`,
      };
    }

    // Access payment transaction properties via payment (algosdk v3 structure)
    // In v3, payment fields are nested: txn.payment.{amount, receiver, closeRemainderTo}
    const paymentFields = (txn as unknown as {
      payment?: {
        amount?: bigint;
        receiver?: { publicKey: Uint8Array };
        closeRemainderTo?: { publicKey: Uint8Array };
      }
    }).payment;

    // Must have zero amount (self-payment for fee coverage)
    const payAmount = paymentFields?.amount ?? BigInt(0);
    if (payAmount > BigInt(0)) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.INVALID_FEE_PAYER}: amount must be 0`,
      };
    }

    // Must not have close remainder to
    if (paymentFields?.closeRemainderTo) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.INVALID_FEE_PAYER}: closeRemainderTo not allowed`,
      };
    }

    // Must not have rekey to
    if (txn.rekeyTo) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.INVALID_FEE_PAYER}: rekeyTo not allowed`,
      };
    }

    // Fee must be reasonable
    const fee = Number(txn.fee ?? 0);
    if (fee > MAX_REASONABLE_FEE) {
      return {
        isValid: false,
        invalidReason: `${VerifyErrorReason.FEE_TOO_HIGH}: ${fee} exceeds maximum ${MAX_REASONABLE_FEE}`,
      };
    }

    return { isValid: true };
  }

  /**
   * Verifies security constraints for ALL transactions in the group.
   *
   * Security checks:
   * 1. No keyreg (key registration) transactions allowed
   * 2. No rekey transactions allowed (unless it's a rekey+rekey-back sandwich)
   * 3. No close-to or close-remainder-to fields allowed on any transaction
   */
  private verifySecurityConstraints(txns: algosdk.SignedTransaction[]): VerifyResponse {
    // Track rekey operations to detect sandwich patterns
    const rekeyOperations: Array<{ index: number; from: string; to: string }> = [];

    for (let i = 0; i < txns.length; i++) {
      const txn = txns[i].txn;
      const sender = algosdk.encodeAddress(txn.sender.publicKey);

      // Check for keyreg transaction type - not allowed
      if (txn.type === "keyreg") {
        return {
          isValid: false,
          invalidReason: `${VerifyErrorReason.SECURITY_KEYREG_NOT_ALLOWED}: Transaction at index ${i} is a key registration transaction`,
        };
      }

      // Check for rekey
      if (txn.rekeyTo) {
        const rekeyTo = algosdk.encodeAddress(txn.rekeyTo.publicKey);
        rekeyOperations.push({ index: i, from: sender, to: rekeyTo });
      }

      // Check for close-to fields based on transaction type
      // These are dangerous as they can drain accounts

      // For payment transactions - check CloseRemainderTo
      if (txn.type === "pay") {
        const paymentFields = (txn as unknown as {
          payment?: {
            closeRemainderTo?: { publicKey: Uint8Array };
          }
        }).payment;

        if (paymentFields?.closeRemainderTo) {
          return {
            isValid: false,
            invalidReason: `${VerifyErrorReason.SECURITY_CLOSE_TO_NOT_ALLOWED}: Transaction at index ${i} has CloseRemainderTo set`,
          };
        }
      }

      // For asset transfer transactions - check AssetCloseTo
      if (txn.type === "axfer") {
        const assetTransfer = (txn as unknown as {
          assetTransfer?: {
            closeTo?: { publicKey: Uint8Array };
          }
        }).assetTransfer;

        if (assetTransfer?.closeTo) {
          return {
            isValid: false,
            invalidReason: `${VerifyErrorReason.SECURITY_CLOSE_TO_NOT_ALLOWED}: Transaction at index ${i} has AssetCloseTo set`,
          };
        }
      }
    }

    // Validate rekey operations - only allow sandwich patterns
    // A sandwich pattern: rekey A->B followed by rekey back to A (same sender)
    if (rekeyOperations.length > 0) {
      // Must have an even number of rekey operations for sandwiches
      if (rekeyOperations.length % 2 !== 0) {
        return {
          isValid: false,
          invalidReason: `${VerifyErrorReason.SECURITY_REKEY_NOT_ALLOWED}: Unbalanced rekey operations detected`,
        };
      }

      // Group rekey operations by sender and verify each pair forms a sandwich
      const rekeysBySender = new Map<string, typeof rekeyOperations>();
      for (const op of rekeyOperations) {
        const existing = rekeysBySender.get(op.from) ?? [];
        existing.push(op);
        rekeysBySender.set(op.from, existing);
      }

      for (const [sender, ops] of rekeysBySender) {
        if (ops.length !== 2) {
          return {
            isValid: false,
            invalidReason: `${VerifyErrorReason.SECURITY_REKEY_NOT_ALLOWED}: Sender ${sender} has ${ops.length} rekey operations, expected 2 for sandwich`,
          };
        }

        // The second rekey's "to" should be the sender (returning authority to self)
        const [first, second] = ops;
        if (second.to !== sender && first.to !== second.to) {
          return {
            isValid: false,
            invalidReason: `${VerifyErrorReason.SECURITY_REKEY_NOT_ALLOWED}: Rekey operations for ${sender} do not form a valid sandwich pattern`,
          };
        }
      }
    }

    return { isValid: true };
  }
}
