/**
 * AVM Facilitator Registration for Exact Payment Protocol
 *
 * Registers AVM exact payment schemes to an x402Facilitator instance.
 */

import { x402Facilitator } from "@x402/core/facilitator";
import type { Network } from "@x402/core/types";
import type { FacilitatorAvmSigner } from "../../signer";
import { ExactAvmScheme } from "./scheme";
import { ExactAvmSchemeV1 } from "../v1/facilitator/scheme";
import { NETWORKS } from "../../v1";

/**
 * Configuration options for registering AVM schemes to an x402Facilitator
 */
export interface AvmFacilitatorConfig {
  /**
   * The AVM signer for facilitator operations (verify and settle)
   */
  signer: FacilitatorAvmSigner;

  /**
   * Networks to register (single network or array of networks)
   * Examples: "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", ["algorand-mainnet", "algorand-testnet"]
   */
  networks: Network | Network[];
}

/**
 * Registers AVM exact payment schemes to an x402Facilitator instance.
 *
 * This function registers:
 * - V2: Specified networks with ExactAvmScheme
 * - V1: All supported AVM networks with ExactAvmSchemeV1
 *
 * @param facilitator - The x402Facilitator instance to register schemes to
 * @param config - Configuration for AVM facilitator registration
 * @returns The facilitator instance for chaining
 *
 * @example
 * ```typescript
 * import { registerExactAvmScheme } from "@x402/avm/exact/facilitator";
 * import { x402Facilitator } from "@x402/core/facilitator";
 * import algosdk from "algosdk";
 *
 * const account = algosdk.mnemonicToSecretKey("your mnemonic...");
 * const signer = toFacilitatorAvmSigner(account);
 *
 * const facilitator = new x402Facilitator();
 *
 * // Single network
 * registerExactAvmScheme(facilitator, {
 *   signer,
 *   networks: "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="
 * });
 *
 * // Multiple networks
 * registerExactAvmScheme(facilitator, {
 *   signer,
 *   networks: [
 *     "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
 *     "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="
 *   ]
 * });
 * ```
 */
export function registerExactAvmScheme(
  facilitator: x402Facilitator,
  config: AvmFacilitatorConfig,
): x402Facilitator {
  // Register V2 scheme with specified networks
  facilitator.register(config.networks, new ExactAvmScheme(config.signer));

  // Register all V1 networks
  facilitator.registerV1(NETWORKS as Network[], new ExactAvmSchemeV1(config.signer));

  return facilitator;
}
