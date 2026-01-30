import algosdk from "algosdk";
import { PaymentRequirements } from "../../../types/verify";
import { AvmSigner } from "../../../types/shared/wallet";
import { createAlgodClient, getUsdcAsaId } from "../../../shared/avm/rpc";
import { encodeToBase64 } from "../../../shared/base64";
import type { Network } from "../../../types/shared/network";
import type { ExactAvmPayload } from "./types";

/**
 * Creates a payment header for AVM (Algorand) exact scheme
 *
 * @param signer - The AVM signer to use for signing transactions
 * @param x402Version - The x402 protocol version
 * @param paymentRequirements - The payment requirements
 * @returns A base64-encoded payment header string
 */
export async function createPaymentHeader(
  signer: AvmSigner,
  x402Version: number,
  paymentRequirements: PaymentRequirements,
): Promise<string> {
  const algodClient = createAlgodClient(paymentRequirements.network as Network);
  const suggestedParams = await algodClient.getTransactionParams().do();

  // Get asset ID from requirements or use default USDC
  const assetId = paymentRequirements.asset
    ? parseInt(paymentRequirements.asset)
    : parseInt(getUsdcAsaId(paymentRequirements.network as Network));

  // Build ASA transfer transaction
  const assetTransferTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
    sender: algosdk.Address.fromString(signer.address),
    receiver: algosdk.Address.fromString(paymentRequirements.payTo),
    amount: BigInt(paymentRequirements.maxAmountRequired),
    assetIndex: assetId,
    suggestedParams,
    note: new Uint8Array(Buffer.from(`x402-payment-v${x402Version}`)),
  });

  // Encode transaction
  const encodedTxn = assetTransferTxn.toByte();

  // Sign transaction
  const signedTxns = await signer.signTransactions([encodedTxn], [0]);
  const signedTxn = signedTxns[0];

  if (!signedTxn) {
    throw new Error("Failed to sign transaction");
  }

  const payload: ExactAvmPayload = {
    paymentGroup: [encodeToBase64(signedTxn)],
    paymentIndex: 0,
  };

  const paymentPayload = {
    x402Version,
    scheme: paymentRequirements.scheme,
    network: paymentRequirements.network,
    payload,
  };

  return encodeToBase64(new TextEncoder().encode(JSON.stringify(paymentPayload)));
}
