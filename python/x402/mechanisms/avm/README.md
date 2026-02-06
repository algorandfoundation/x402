# x402 AVM Mechanism

Algorand implementation of the x402 payment protocol using the **Exact** payment scheme with ASA (Algorand Standard Asset) transfers.

## Installation

```bash
uv add x402[avm]
```

## Overview

Three components for handling x402 payments on Algorand:

- **Client** (`ExactAvmClientScheme`) - Creates signed ASA transfer transactions
- **Server** (`ExactAvmServerScheme`) - Builds payment requirements, parses prices
- **Facilitator** (`ExactAvmFacilitatorScheme`) - Verifies transactions, signs fee payer, submits

## Quick Start

### Client

```python
import base64
import algosdk
from x402 import x402Client
from x402.mechanisms.avm.exact import ExactAvmScheme

# Decode Base64 private key (64 bytes: 32-byte seed + 32-byte public key)
secret_key = base64.b64decode(os.environ["AVM_PRIVATE_KEY"])
address = algosdk.encoding.encode_address(secret_key[32:])

# Implement ClientAvmSigner protocol
class MyAlgorandSigner:
    def __init__(self, sk: bytes, addr: str):
        self._secret_key = sk
        self._address = addr

    @property
    def address(self) -> str:
        return self._address

    def sign_transactions(self, unsigned_txns, indexes_to_sign):
        result = []
        for i, txn_bytes in enumerate(unsigned_txns):
            if i in indexes_to_sign:
                txn = algosdk.encoding.msgpack_decode(txn_bytes)
                signed = txn.sign(self._secret_key)
                result.append(algosdk.encoding.msgpack_encode(signed))
            else:
                result.append(None)
        return result

signer = MyAlgorandSigner(secret_key, address)
client = x402Client()
client.register("algorand:*", ExactAvmScheme(signer=signer))

payload = await client.create_payment_payload(payment_required)
```

### Server

```python
from x402 import x402ResourceServer
from x402.mechanisms.avm.exact import ExactAvmServerScheme

server = x402ResourceServer(facilitator_client)
server.register("algorand:*", ExactAvmServerScheme())
```

### Facilitator

```python
import base64
import algosdk
from x402 import x402Facilitator
from x402.mechanisms.avm.exact import ExactAvmFacilitatorScheme
from x402.mechanisms.avm import ALGORAND_MAINNET_CAIP2

# Decode Base64 private key and create Algod client
secret_key = base64.b64decode(os.environ["AVM_PRIVATE_KEY"])
address = algosdk.encoding.encode_address(secret_key[32:])
algod_client = algosdk.v2client.algod.AlgodClient("", "https://mainnet-api.algonode.cloud")

# Implement FacilitatorAvmSigner protocol (see examples/python/facilitator for full impl)
# Must implement: get_addresses, sign_transaction, sign_group,
#                 simulate_group, send_group, confirm_transaction

facilitator = x402Facilitator()
facilitator.register(
    [ALGORAND_MAINNET_CAIP2],  # "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="
    ExactAvmFacilitatorScheme(signer=signer),
)
```

## Exports

### `x402.mechanisms.avm.exact`

| Export | Description |
|--------|-------------|
| `ExactAvmScheme` | Client scheme (alias for `ExactAvmClientScheme`) |
| `ExactAvmClientScheme` | Client-side transaction creation |
| `ExactAvmServerScheme` | Server-side requirement building |
| `ExactAvmFacilitatorScheme` | Facilitator verification/settlement |
| `register_exact_avm_client()` | Helper to register client |
| `register_exact_avm_server()` | Helper to register server |
| `register_exact_avm_facilitator()` | Helper to register facilitator |

### `x402.mechanisms.avm`

| Export | Description |
|--------|-------------|
| `ClientAvmSigner` | Protocol for client signers (implement with algosdk) |
| `FacilitatorAvmSigner` | Protocol for facilitator signers (implement with algosdk) |
| `NETWORK_CONFIGS` | Network configuration mapping |
| `V1_NETWORKS` | List of V1 network names |
| `ALGORAND_MAINNET_CAIP2` | Mainnet CAIP-2 identifier |
| `ALGORAND_TESTNET_CAIP2` | Testnet CAIP-2 identifier |

## Supported Networks

**V2 Networks** (CAIP-2 format):
- `algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=` - Mainnet
- `algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=` - Testnet
- `algorand:*` - Wildcard (all Algorand networks)

**V1 Networks** (legacy names):
- `algorand-mainnet` - Mainnet
- `algorand-testnet` - Testnet

## Asset Support

Supports Algorand Standard Assets (ASAs):
- USDC (primary):
  - Mainnet: ASA ID `31566704`
  - Testnet: ASA ID `10458941`
- Any ASA with opt-in enabled on receiver

## Technical Details

### Transaction Structure

The Exact scheme creates atomic transaction groups:

**Without Fee Abstraction** (client pays fees):
1. ASA transfer transaction (signed by client)

**With Fee Abstraction** (facilitator pays fees):
1. Fee payer transaction: self-payment with pooled fees (signed by facilitator)
2. ASA transfer transaction with zero fee (signed by client)

### Fee Pooling

When using fee abstraction, fees are pooled in the first transaction:
```
pooled_fee = min_fee × transaction_count
```

Example: For a 2-transaction group with 1000 microalgo min fee:
- Fee payer transaction: `fee = 2000` (covers both)
- ASA transfer: `fee = 0`

### Atomic Groups

Algorand natively supports atomic transaction groups:
- Up to 16 transactions per group
- All-or-nothing execution (no partial settlement)
- Group ID computed from all transaction hashes

### Instant Finality

Algorand has no consensus forks - once a transaction is in a block, it's final. No waiting for confirmations.

### Security Checks

The facilitator validates:
- No `rekey` operations (prevents key theft)
- No `close-to` operations (prevents account draining)
- No `keyreg` transactions (prevents consensus attacks)
- Fee payer not transferring funds
- Group size ≤ 16 transactions
- Genesis hash matches network
- All group IDs match

## Verification Flow

Per the Algorand exact scheme specification:

1. Check `paymentGroup` contains ≤16 transactions
2. Decode all transactions from the group
3. Locate payment transaction (`paymentIndex`):
   - Verify `aamt` ≥ `requirements.amount`
   - Verify `arcv` matches `requirements.payTo`
4. If `feePayer` in requirements:
   - Locate fee payer transaction
   - Verify `type` is "pay"
   - Verify `close`, `rekey`, `amt` are omitted/zero
   - Verify fee is reasonable
   - Sign the transaction
5. Simulate group to verify success

## Payment Payload Format

```json
{
  "paymentIndex": 1,
  "paymentGroup": [
    "base64-encoded-unsigned-fee-payer-txn",
    "base64-encoded-signed-asa-transfer-txn"
  ]
}
```

## Error Codes

| Error | Description |
|-------|-------------|
| `unsupported_scheme` | Scheme is not "exact" |
| `network_mismatch` | Network in payload doesn't match requirements |
| `invalid_exact_avm_payload_payment_index` | Payment index out of bounds |
| `invalid_exact_avm_payload_group_too_large` | More than 16 transactions |
| `invalid_exact_avm_payload_empty_group` | Empty transaction group |
| `invalid_exact_avm_payload_asset_id_mismatch` | ASA ID doesn't match |
| `invalid_exact_avm_payload_recipient_mismatch` | Receiver doesn't match payTo |
| `invalid_exact_avm_payload_amount_insufficient` | Amount less than required |
| `invalid_exact_avm_payload_rekey_detected` | Rekey operation found |
| `invalid_exact_avm_payload_close_to_detected` | Close-to operation found |
| `fee_payer_not_managed_by_facilitator` | Fee payer not in facilitator's signers |
| `transaction_simulation_failed` | Simulation returned error |
| `transaction_failed` | On-chain submission failed |
