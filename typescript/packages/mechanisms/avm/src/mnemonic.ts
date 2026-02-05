/**
 * AVM (Algorand) Mnemonic Utilities for x402 Payment Protocol
 *
 * Supports both Algorand native 25-word mnemonics and BIP-39 24-word mnemonics.
 * BIP-39 mnemonics use BIP32-Ed25519 derivation with the Algorand derivation path.
 *
 * @see https://acrobat.adobe.com/id/urn:aaid:sc:EU:04fe29b0-ea1a-478b-a886-9bb558a5242a - BIP32-Ed25519 spec
 * @see https://github.com/satoshilabs/slips/blob/master/slip-0044.md - Coin type 283 = Algorand
 */

import algosdk from "algosdk";
import { mnemonicToSeedSync, validateMnemonic } from "@scure/bip39";
import { wordlist } from "@scure/bip39/wordlists/english";
import {
  fromSeed,
  deriveKey,
  getPublicKey,
  getAlgorandBIP44Path,
  BIP32DerivationType,
  signWithExtendedKey,
} from "./bip32-ed25519";

/**
 * Extended Algorand account with BIP32-Ed25519 key material
 * Used for accounts derived from BIP-39 mnemonics that require custom signing
 */
export interface ExtendedAlgorandAccount extends algosdk.Account {
  /** Extended key bytes (kL || kR || chainCode) - 96 bytes, for custom signing */
  extendedKey?: Uint8Array;
  /** Whether this account requires custom BIP32-Ed25519 signing */
  useExtendedSigning?: boolean;
}

/**
 * Algorand BIP-44 derivation path
 * m/44'/283'/0'/0/0
 * - 44' = BIP-44 purpose
 * - 283' = Algorand coin type (registered in SLIP-44)
 * - 0' = account index
 * - 0 = change (external chain, non-hardened)
 * - 0 = address index (non-hardened)
 *
 * Note: Uses BIP32-Ed25519 derivation (Khovratovich/Peikert specification).
 * This provides proper ed25519 HD key derivation with both hardened and non-hardened support.
 * Additional addresses can be derived by incrementing the address index.
 */
export const ALGORAND_DERIVATION_PATH = "m/44'/283'/0'/0/0";

/**
 * Result of mnemonic type detection
 */
export type MnemonicType = "algorand-25" | "bip39-24" | "invalid";

/**
 * Detects the type of mnemonic based on word count and validity
 *
 * @param mnemonic - The mnemonic phrase to check
 * @returns The detected mnemonic type
 *
 * @example
 * ```typescript
 * detectMnemonicType("abandon abandon ... about") // "bip39-24"
 * detectMnemonicType("abandon abandon ... abandon about") // "algorand-25"
 * detectMnemonicType("invalid mnemonic") // "invalid"
 * ```
 */
export function detectMnemonicType(mnemonic: string): MnemonicType {
  const words = mnemonic.trim().split(/\s+/);

  if (words.length === 25) {
    // Algorand native 25-word mnemonic
    try {
      algosdk.mnemonicToSecretKey(mnemonic);
      return "algorand-25";
    } catch {
      return "invalid";
    }
  }

  if (words.length === 24) {
    // BIP-39 24-word mnemonic
    if (validateMnemonic(mnemonic, wordlist)) {
      return "bip39-24";
    }
    return "invalid";
  }

  return "invalid";
}

/**
 * Derives an Algorand account from a BIP-39 24-word mnemonic
 *
 * Uses BIP32-Ed25519 derivation with the standard Algorand derivation path.
 * This is compatible with wallets like Lute, Pera, Defly, and other BIP-39 compatible Algorand wallets.
 *
 * @param mnemonic - BIP-39 24-word mnemonic phrase
 * @param accountIndex - Optional account index (default: 0)
 * @returns Algorand account object
 * @throws Error if the mnemonic is invalid
 *
 * @example
 * ```typescript
 * const account = deriveAlgorandFromBip39("abandon abandon ... about");
 * console.log(account.addr); // Algorand address
 * ```
 */
export function deriveAlgorandFromBip39(
  mnemonic: string,
  accountIndex: number = 0,
): ExtendedAlgorandAccount {
  // Validate the mnemonic
  if (!validateMnemonic(mnemonic, wordlist)) {
    throw new Error("Invalid BIP-39 mnemonic phrase");
  }

  // Convert mnemonic to seed (BIP-39) - this produces 64 bytes
  // BIP32-Ed25519 can work with either 32 or 64 byte seeds
  // The fromSeed function hashes the seed with SHA-512, so the input size is flexible
  const seed = mnemonicToSeedSync(mnemonic);

  // Derive the root key using BIP32-Ed25519
  const rootKey = fromSeed(seed);

  // Get the BIP44 path for Algorand
  const bip44Path = getAlgorandBIP44Path(0, accountIndex);

  // Derive the key at the specified path using Peikert derivation (9 bits)
  // This allows for more derivation levels while maintaining security
  const derivedKey = deriveKey(rootKey, bip44Path, BIP32DerivationType.Peikert);

  // Get the public key from the derived extended key
  const publicKey = getPublicKey(derivedKey);

  // The derived scalar (left 32 bytes) is used as the private key seed
  // Note: In BIP32-Ed25519, the scalar IS the private key (already processed/clamped)
  const privateKeySeed = derivedKey.subarray(0, 32);

  // Algorand's secret key format is 64 bytes: [32-byte seed | 32-byte public key]
  // This matches the NaCl sign.keyPair.fromSeed format used internally by algosdk
  const secretKey = new Uint8Array(64);
  secretKey.set(privateKeySeed, 0);
  secretKey.set(publicKey, 32);

  // Create the Address object from the public key
  // In algosdk v3, Address is a class that wraps the public key bytes
  const address = new algosdk.Address(publicKey);

  return {
    addr: address,
    sk: secretKey,
    // Store the extended key for custom signing (needed for BIP32-Ed25519)
    extendedKey: new Uint8Array(derivedKey),
    useExtendedSigning: true,
  };
}

/**
 * Sign a transaction using BIP32-Ed25519 extended key
 *
 * This function must be used for signing transactions with BIP-39 derived accounts
 * because algosdk's standard signing re-hashes the key, which produces incorrect
 * signatures for BIP32-Ed25519 derived scalars.
 *
 * @param txn - The transaction to sign
 * @param extendedKey - Extended key bytes (kL || kR || chainCode) - 96 bytes
 * @returns Signed transaction
 */
export function signTransactionWithExtendedKey(
  txn: algosdk.Transaction,
  extendedKey: Uint8Array,
): algosdk.SignedTransaction {
  // Get the bytes to sign: "TX" prefix + msgpack encoded transaction
  const txnBytes = txn.toByte();
  const bytesToSign = new Uint8Array(2 + txnBytes.length);
  bytesToSign[0] = "T".charCodeAt(0);
  bytesToSign[1] = "X".charCodeAt(0);
  bytesToSign.set(txnBytes, 2);

  // Sign with the extended key using BIP32-Ed25519 signing
  const signature = signWithExtendedKey(extendedKey, bytesToSign);

  // Create signed transaction with the signature
  return new algosdk.SignedTransaction({ txn, sig: signature });
}

/**
 * Converts any supported mnemonic format to an Algorand account
 *
 * Automatically detects whether the input is a 25-word Algorand native mnemonic
 * or a 24-word BIP-39 mnemonic and derives the account accordingly.
 *
 * @param mnemonic - Mnemonic phrase (24 or 25 words)
 * @param accountIndex - Account index for BIP-39 derivation (ignored for 25-word mnemonics)
 * @returns Algorand account object
 * @throws Error if the mnemonic is invalid or unsupported
 *
 * @example
 * ```typescript
 * // Works with Algorand native 25-word mnemonic
 * const account1 = mnemonicToAlgorandAccount("abandon abandon ... abandon about");
 *
 * // Also works with BIP-39 24-word mnemonic
 * const account2 = mnemonicToAlgorandAccount("abandon abandon ... about");
 *
 * // Derive additional accounts from BIP-39 mnemonic
 * const account3 = mnemonicToAlgorandAccount("abandon abandon ... about", 1);
 * ```
 */
export function mnemonicToAlgorandAccount(
  mnemonic: string,
  accountIndex: number = 0,
): algosdk.Account {
  const mnemonicType = detectMnemonicType(mnemonic);

  switch (mnemonicType) {
    case "algorand-25":
      // Algorand native mnemonic - use algosdk directly
      // Note: accountIndex is ignored for 25-word mnemonics as they encode a single key
      return algosdk.mnemonicToSecretKey(mnemonic);

    case "bip39-24":
      // BIP-39 mnemonic - use BIP32-Ed25519 derivation
      return deriveAlgorandFromBip39(mnemonic, accountIndex);

    case "invalid":
    default:
      throw new Error(
        "Invalid mnemonic: must be a valid 24-word BIP-39 mnemonic or 25-word Algorand mnemonic",
      );
  }
}

/**
 * Validates a mnemonic phrase
 *
 * @param mnemonic - The mnemonic phrase to validate
 * @returns True if the mnemonic is valid (either 24-word BIP-39 or 25-word Algorand)
 *
 * @example
 * ```typescript
 * isValidMnemonic("abandon abandon ... about") // true (BIP-39)
 * isValidMnemonic("abandon abandon ... abandon about") // true (Algorand)
 * isValidMnemonic("invalid words") // false
 * ```
 */
export function isValidMnemonic(mnemonic: string): boolean {
  return detectMnemonicType(mnemonic) !== "invalid";
}

/**
 * Gets the word count from a mnemonic phrase
 *
 * @param mnemonic - The mnemonic phrase
 * @returns Number of words in the mnemonic
 */
export function getMnemonicWordCount(mnemonic: string): number {
  return mnemonic.trim().split(/\s+/).length;
}
