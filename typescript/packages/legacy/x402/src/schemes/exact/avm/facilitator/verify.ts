import algosdk from "algosdk";
import { PaymentPayload, PaymentRequirements, VerifyResponse } from "../../../../types/verify";
import { AvmSigner } from "../../../../types/shared/wallet";
import { decodeFromBase64 } from "../../../../shared/base64";
import { isExactAvmPayload, ExactAvmPayload } from "../types";

/**
 * Verifies an AVM (Algorand) exact scheme payment payload
 *
 * @param _signer - The AVM signer (unused for verification, but kept for API consistency)
 * @param paymentPayload - The payment payload to verify
 * @param paymentRequirements - The payment requirements to verify against
 * @returns A verification response indicating if the payment is valid
 */
export async function verify(
  _signer: AvmSigner,
  paymentPayload: PaymentPayload,
  paymentRequirements: PaymentRequirements,
): Promise<VerifyResponse> {
  const rawPayload = paymentPayload.payload;

  if (!isExactAvmPayload(rawPayload)) {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload",
      payer: "",
    };
  }

  const avmPayload = rawPayload as ExactAvmPayload;
  const { paymentGroup, paymentIndex } = avmPayload;

  // Check bounds
  if (paymentIndex < 0 || paymentIndex >= paymentGroup.length) {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload_payment_index",
      payer: "",
    };
  }

  // Decode payment transaction
  let paymentTxn: algosdk.SignedTransaction;
  let payer = "";
  try {
    const txnBytes = decodeFromBase64(paymentGroup[paymentIndex]);
    paymentTxn = algosdk.decodeSignedTransaction(txnBytes);
    payer = algosdk.encodeAddress(paymentTxn.txn.sender.publicKey);
  } catch {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload_transaction_encoding",
      payer: "",
    };
  }

  const txn = paymentTxn.txn;

  // Verify it's an asset transfer
  if (txn.type !== "axfer") {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload_transaction_type",
      payer,
    };
  }

  // Verify amount
  const assetAmount = (txn as unknown as { assetAmount?: bigint }).assetAmount ?? BigInt(0);
  const amount = assetAmount.toString();
  if (amount !== paymentRequirements.maxAmountRequired) {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload_amount_mismatch",
      payer,
    };
  }

  // Verify receiver
  const assetReceiver = (txn as unknown as { assetReceiver?: { publicKey: Uint8Array } }).assetReceiver;
  const receiver = assetReceiver
    ? algosdk.encodeAddress(assetReceiver.publicKey)
    : "";
  if (receiver !== paymentRequirements.payTo) {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload_receiver_mismatch",
      payer,
    };
  }

  // Verify asset
  const assetIndex = (txn as unknown as { assetIndex?: bigint }).assetIndex;
  const assetId = assetIndex?.toString() ?? "";
  if (assetId !== paymentRequirements.asset) {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload_asset_mismatch",
      payer,
    };
  }

  // Verify signature exists
  if (!paymentTxn.sig && !paymentTxn.msig && !paymentTxn.lsig) {
    return {
      isValid: false,
      invalidReason: "invalid_exact_avm_payload_not_signed",
      payer,
    };
  }

  return { isValid: true, payer };
}
