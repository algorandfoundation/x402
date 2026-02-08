# x402 Python Examples

Examples for the x402 Python SDK with EVM, SVM, and AVM (Algorand) support.

## Quick Start

```bash
cd clients/httpx
cp .env-local .env
# Edit .env with your EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, and/or AVM_PRIVATE_KEY
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
- Private key format: Base64-encoded 64-byte key (32-byte seed + 32-byte public key)

## Legacy SDK

- **[legacy/](./legacy/)** - V1 SDK examples (for backward compatibility)

## Learn More

- [Python SDK](../../python/x402/)
- [x402 Protocol](https://x402.org)
