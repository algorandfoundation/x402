/**
 * AVM Client Scheme V1 for Exact Payment Protocol (Backward Compatibility)
 *
 * Provides V1 API compatibility for Algorand ASA transfers.
 */

import algosdk from "algosdk";
import type {
  Network,
  PaymentPayload,
  PaymentRequirements,
  SchemeNetworkClient,
} from "@x402/core/types";
import { PaymentRequirementsV1 } from "@x402/core/types/v1";
import type { ClientAvmSigner, ClientAvmConfig } from "../../../signer";
import type { ExactAvmPayloadV1 } from "../../../types";
import { createAlgodClient, encodeTransaction } from "../../../utils";
import { V1_TO_CAIP2, USDC_CONFIG, DEFAULT_ALGOD_TESTNET } from "../../../constants";

/**
 * AVM client implementation for the Exact payment scheme (V1).
 *
 * Provides backward compatibility with V1 x402 API while using the same
 * atomic transaction group structure as V2.
 */
export class ExactAvmSchemeV1 implements SchemeNetworkClient {
  readonly scheme = "exact";

  /**
   * Creates a new ExactAvmSchemeV1 instance.
   *
   * @param signer - The AVM signer for client operations
   * @param config - Optional configuration for Algod client
   */
  constructor(
    private readonly signer: ClientAvmSigner,
    private readonly config?: ClientAvmConfig,
  ) {}

  /**
   * Creates a payment payload for the Exact scheme (V1).
   *
   * @param x402Version - The x402 protocol version
   * @param paymentRequirements - The payment requirements
   * @returns Promise resolving to a payment payload
   */
  async createPaymentPayload(
    x402Version: number,
    paymentRequirements: PaymentRequirements,
  ): Promise<
    Pick<PaymentPayload, "x402Version" | "payload"> & { scheme: string; network: Network }
  > {
    const selectedV1 = paymentRequirements as unknown as PaymentRequirementsV1;
    const v1Network = selectedV1.network;

    // Convert V1 network to CAIP-2 for internal use
    const caip2Network = V1_TO_CAIP2[v1Network] ?? v1Network;

    // Get Algod client
    const algodClient = (
      this.config?.algodClient ??
      createAlgodClient(
        caip2Network as Network,
        this.config?.algodUrl ?? DEFAULT_ALGOD_TESTNET,
        this.config?.algodToken,
      )
    ) as algosdk.Algodv2;

    // Get suggested params
    const suggestedParams = await algodClient.getTransactionParams().do();

    // Get asset ID
    const assetId = this.getAssetId(selectedV1.asset, caip2Network);

    // Build ASA transfer transaction
    const assetTransferTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
      sender: algosdk.Address.fromString(this.signer.address),
      receiver: algosdk.Address.fromString(selectedV1.payTo),
      amount: BigInt(selectedV1.maxAmountRequired),
      assetIndex: Number(assetId),
      suggestedParams,
      note: new Uint8Array(Buffer.from(`x402-payment-v${x402Version}`)),
    });

    // Encode transaction
    const encodedTxn = assetTransferTxn.toByte();

    // Sign transaction
    const signedTxns = await this.signer.signTransactions([encodedTxn], [0]);
    const signedTxn = signedTxns[0];

    if (!signedTxn) {
      throw new Error("Failed to sign transaction");
    }

    const payload: ExactAvmPayloadV1 = {
      paymentGroup: [encodeTransaction(signedTxn)],
      paymentIndex: 0,
    };

    return {
      x402Version,
      scheme: selectedV1.scheme,
      network: selectedV1.network,
      payload: payload as unknown as Record<string, unknown>,
    };
  }

  /**
   * Gets the asset ID from the requirements or defaults to USDC
   */
  private getAssetId(asset: string, network: string): string {
    if (/^\d+$/.test(asset)) {
      return asset;
    }

    const usdcConfig = USDC_CONFIG[network];
    if (usdcConfig) {
      return usdcConfig.asaId;
    }

    return asset;
  }
}
