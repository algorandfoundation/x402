/**
 * AVM (Algorand) Mnemonic Utilities for x402 Payment Protocol
 *
 * Supports both Algorand native 25-word mnemonics and BIP-39 24-word mnemonics.
 * BIP-39 mnemonics use SLIP-0010 ed25519 derivation with the Algorand derivation path.
 *
 * @see https://github.com/satoshilabs/slips/blob/master/slip-0010.md - SLIP-0010 spec
 * @see https://github.com/satoshilabs/slips/blob/master/slip-0044.md - Coin type 283 = Algorand
 */

import algosdk from "algosdk";
import { HDKey } from "@scure/bip32";
import { mnemonicToSeedSync, validateMnemonic } from "@scure/bip39";
import { wordlist } from "@scure/bip39/wordlists/english";
import { ed25519 } from "@noble/curves/ed25519";

/**
 * Algorand BIP-44 derivation path
 * m/44'/283'/0'/0'
 * - 44' = BIP-44 purpose
 * - 283' = Algorand coin type (registered in SLIP-44)
 * - 0' = account index
 * - 0' = change (external chain)
 *
 * Note: Algorand wallets typically use the first key at this path.
 * Some wallets may derive additional accounts by incrementing the account index.
 */
export const ALGORAND_DERIVATION_PATH = "m/44'/283'/0'/0'";

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
 * Uses SLIP-0010 ed25519 derivation with the standard Algorand derivation path.
 * This is compatible with wallets like Pera, Defly, and other BIP-39 compatible Algorand wallets.
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
): algosdk.Account {
  // Validate the mnemonic
  if (!validateMnemonic(mnemonic, wordlist)) {
    throw new Error("Invalid BIP-39 mnemonic phrase");
  }

  // Convert mnemonic to seed (BIP-39)
  const seed = mnemonicToSeedSync(mnemonic);

  // Derive the master key using SLIP-0010 for ed25519
  const masterKey = HDKey.fromMasterSeed(seed);

  // Build the derivation path with optional account index
  // Standard path: m/44'/283'/accountIndex'/0'
  const path =
    accountIndex === 0
      ? ALGORAND_DERIVATION_PATH
      : `m/44'/283'/${accountIndex}'/0'`;

  // Derive the key at the specified path
  const derivedKey = masterKey.derive(path);

  if (!derivedKey.privateKey) {
    throw new Error("Failed to derive private key from mnemonic");
  }

  // The derived private key (seed) is 32 bytes
  const privateKeySeed = derivedKey.privateKey;

  // Derive the public key from the private key seed using ed25519
  const publicKey = ed25519.getPublicKey(privateKeySeed);

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
  };
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
      // BIP-39 mnemonic - use SLIP-0010 derivation
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
