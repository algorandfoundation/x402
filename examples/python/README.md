# x402 Python Examples

Examples for the x402 Python SDK with EVM, SVM, and AVM (Algorand) support.

## Quick Start

```bash
cd clients/httpx
cp .env-local .env
# Edit .env with your EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, and/or AVM_MNEMONIC
uv sync
uv run python main.py
```

## V2 SDK (Recommended)

### Clients
- **[clients/httpx/](./clients/httpx/)** - Async HTTP client with httpx
- **[clients/requests/](./clients/requests/)** - Sync HTTP client with requests
- **[clients/custom/](./clients/custom/)** - Manual payment handling
- **[clients/advanced/](./clients/advanced/)** - Hooks, selectors, and builder patterns

### Servers
- **[servers/fastapi/](./servers/fastapi/)** - FastAPI server with payment middleware
- **[servers/flask/](./servers/flask/)** - Flask server with payment middleware
- **[servers/custom/](./servers/custom/)** - Manual payment handling
- **[servers/advanced/](./servers/advanced/)** - Dynamic pricing, hooks, and more

### Facilitator
- **[facilitator/](./facilitator/)** - Payment facilitator service

## Supported Networks

### EVM (Ethereum/Base)
- Network: `eip155:84532` (Base Sepolia)
- Private key format: `0x...` hex string

### SVM (Solana)
- Network: `solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` (Devnet)
- Private key format: Base58 string

### AVM (Algorand)
- Network: `algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=` (Testnet)
- Private key format: 24-word BIP-39 or 25-word Algorand native mnemonic

## Environment Variables

### Client Examples
```bash
# At least one private key required
EVM_PRIVATE_KEY=0x...
SVM_PRIVATE_KEY=...base58...
AVM_MNEMONIC=word1 word2 ... (24-word BIP-39 or 25-word Algorand)

RESOURCE_SERVER_URL=http://localhost:4021
ENDPOINT_PATH=/weather
```

### Server Examples
```bash
# At least one address required
EVM_ADDRESS=0x...
SVM_ADDRESS=...base58...
AVM_ADDRESS=ALGORANDADDRESS...

FACILITATOR_URL=https://x402.org/facilitator
```

### Facilitator Example
```bash
PORT=4022

# At least one key required
EVM_PRIVATE_KEY=0x...
EVM_RPC_URL=https://sepolia.base.org

SVM_PRIVATE_KEY=...base58...

AVM_MNEMONIC=word1 word2 ... (24-word BIP-39 or 25-word Algorand)
ALGOD_SERVER=https://testnet-api.algonode.cloud
ALGOD_TOKEN=
```

## Legacy SDK

- **[legacy/](./legacy/)** - V1 SDK examples (for backward compatibility)

## Learn More

- [Python SDK](../../python/x402/)
- [x402 Protocol](https://x402.org)
