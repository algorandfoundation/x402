import algosdk from "algosdk";

/**
 * AVM (Algorand) signer interface
 */
export interface AvmSigner {
  address: string;
  signTransactions(
    txns: Uint8Array[],
    indexesToSign?: number[],
  ): Promise<(Uint8Array | null)[]>;
}

/**
 * Type guard to check if a wallet is an AVM signer
 */
export function isSignerWallet(wallet: unknown): wallet is AvmSigner {
  return (
    typeof wallet === "object" &&
    wallet !== null &&
    "address" in wallet &&
    typeof (wallet as AvmSigner).address === "string" &&
    "signTransactions" in wallet &&
    typeof (wallet as AvmSigner).signTransactions === "function"
  );
}

/**
 * Creates an AVM signer from an algosdk account
 */
export function createSignerFromAccount(account: algosdk.Account): AvmSigner {
  return {
    address: account.addr.toString(),
    async signTransactions(txns: Uint8Array[], indexesToSign?: number[]) {
      const indexes = indexesToSign ?? txns.map((_, i) => i);
      const signed: (Uint8Array | null)[] = [];

      for (let i = 0; i < txns.length; i++) {
        if (indexes.includes(i)) {
          const decodedTxn = algosdk.decodeUnsignedTransaction(txns[i]);
          const signedTxn = algosdk.signTransaction(decodedTxn, account.sk);
          signed.push(signedTxn.blob);
        } else {
          signed.push(null);
        }
      }

      return signed;
    },
  };
}

/**
 * Creates an AVM signer from a mnemonic
 */
export async function createSignerFromMnemonic(mnemonic: string): Promise<AvmSigner> {
  const account = algosdk.mnemonicToSecretKey(mnemonic);
  return createSignerFromAccount(account);
}
