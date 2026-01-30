import algosdk from "algosdk";
import { PaymentPayload, PaymentRequirements, SettleResponse } from "../../../../types/verify";
import { AvmSigner } from "../../../../types/shared/wallet";
import { createAlgodClient } from "../../../../shared/avm/rpc";
import { decodeFromBase64 } from "../../../../shared/base64";
import { verify } from "./verify";
import { isExactAvmPayload, ExactAvmPayload } from "../types";
import type { Network } from "../../../../types/shared/network";

/**
 * Settles an AVM (Algorand) exact scheme payment
 *
 * @param signer - The AVM signer (used for verification)
 * @param paymentPayload - The payment payload to settle
 * @param paymentRequirements - The payment requirements
 * @returns A settlement response indicating success or failure
 */
export async function settle(
  signer: AvmSigner,
  paymentPayload: PaymentPayload,
  paymentRequirements: PaymentRequirements,
): Promise<SettleResponse> {
  // First verify the payment
  const verification = await verify(signer, paymentPayload, paymentRequirements);
  if (!verification.isValid) {
    return {
      success: false,
      errorReason: verification.invalidReason,
      transaction: "",
      network: paymentRequirements.network,
      payer: verification.payer,
    };
  }

  const rawPayload = paymentPayload.payload;
  if (!isExactAvmPayload(rawPayload)) {
    return {
      success: false,
      errorReason: "invalid_exact_avm_payload",
      transaction: "",
      network: paymentRequirements.network,
      payer: verification.payer,
    };
  }

  const avmPayload = rawPayload as ExactAvmPayload;
  const { paymentGroup, paymentIndex } = avmPayload;

  try {
    const algodClient = createAlgodClient(paymentRequirements.network as Network);

    // Decode all signed transactions
    const signedTxns = paymentGroup.map(encoded => decodeFromBase64(encoded));

    // Combine transactions for submission
    const combined = new Uint8Array(
      signedTxns.reduce((acc, txn) => acc + txn.length, 0),
    );
    let offset = 0;
    for (const txn of signedTxns) {
      combined.set(txn, offset);
      offset += txn.length;
    }

    // Submit transaction
    const response = await algodClient.sendRawTransaction(combined).do();
    const txId = response.txid;

    // Wait for confirmation (Algorand has instant finality)
    await algosdk.waitForConfirmation(algodClient, txId, 4);

    // Get the payment transaction ID
    const paymentTxnBytes = signedTxns[paymentIndex];
    const paymentStxn = algosdk.decodeSignedTransaction(paymentTxnBytes);
    const paymentTxId = paymentStxn.txn.txID();

    return {
      success: true,
      transaction: paymentTxId,
      network: paymentRequirements.network,
      payer: verification.payer,
    };
  } catch {
    return {
      success: false,
      errorReason: "settle_exact_avm_transaction_failed",
      transaction: "",
      network: paymentRequirements.network,
      payer: verification.payer,
    };
  }
}
