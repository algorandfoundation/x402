"""Custom token/money parser example."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.avm.exact import ExactAvmServerScheme
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import AssetAmount, Network
from x402.server import x402ResourceServer

load_dotenv()

# Config
EVM_ADDRESS = os.getenv("EVM_ADDRESS")
AVM_ADDRESS = os.getenv("AVM_ADDRESS")
AVM_NETWORK: Network = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="  # Algorand Testnet
EVM_NETWORK: Network = "eip155:84532"  # Base Sepolia
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")

if not EVM_ADDRESS or not AVM_ADDRESS:
    raise ValueError("Missing required environment variables (EVM_ADDRESS, AVM_ADDRESS)")


def custom_money_parser(amount: float, network: str) -> AssetAmount | None:
    """Custom money parser for Gnosis Chain using Wrapped XDAI.

    NOTE: Wrapped XDAI is not EIP-3009 compliant. This is for demonstration.
    """
    if network == "eip155:100":  # Gnosis Chain
        return AssetAmount(
            amount=str(int(amount * 1e18)),
            asset="0xe91d153e0b41518a2ce8dd3d7944fa863463a97d",  # WXDAI
            extra={"token": "Wrapped XDAI"},
        )
    return None


class WeatherReport(BaseModel):
    weather: str
    temperature: int


class WeatherResponse(BaseModel):
    report: WeatherReport


app = FastAPI()

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)

# Register EVM scheme with custom money parser
evm_scheme = ExactEvmServerScheme()
evm_scheme.register_money_parser(custom_money_parser)
server.register(EVM_NETWORK, evm_scheme)


def custom_avm_money_parser(amount: float, network: str) -> AssetAmount | None:
    """Custom money parser for Algorand using custom ASA.

    This demonstrates custom ASA asset configuration.
    """
    if network.startswith("algorand:"):
        # Example: Custom ASA with 6 decimals
        return AssetAmount(
            amount=str(int(amount * 1e6)),
            asset="12345678",  # Example ASA ID
            extra={"token": "Custom ASA", "decimals": 6},
        )
    return None


# Register AVM scheme with custom money parser
avm_scheme = ExactAvmServerScheme()
avm_scheme.register_money_parser(custom_avm_money_parser)
server.register(AVM_NETWORK, avm_scheme)

custom_token_accepts = [
    PaymentOption(
        scheme="exact",
        pay_to=AVM_ADDRESS,
        price="$0.001",
        network=AVM_NETWORK,
    ),
    PaymentOption(
        scheme="exact",
        pay_to=EVM_ADDRESS,
        price="$0.001",
        network=EVM_NETWORK,
    ),
]

routes = {
    "GET /weather": RouteConfig(
        accepts=custom_token_accepts,
    ),
}
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


@app.get("/weather")
async def get_weather(city: str = "San Francisco") -> WeatherResponse:
    return WeatherResponse(report=WeatherReport(weather="sunny", temperature=70))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4021)
