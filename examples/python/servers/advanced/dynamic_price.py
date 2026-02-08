"""Dynamic pricing example."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import HTTPRequestContext, RouteConfig
from x402.mechanisms.avm import ALGORAND_TESTNET_CAIP2
from x402.mechanisms.avm.exact import ExactAvmServerScheme
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

load_dotenv()

# Config
EVM_ADDRESS = os.getenv("EVM_ADDRESS")
AVM_ADDRESS = os.getenv("AVM_ADDRESS")
AVM_NETWORK: Network = ALGORAND_TESTNET_CAIP2
EVM_NETWORK: Network = "eip155:84532"  # Base Sepolia
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")

if not EVM_ADDRESS or not AVM_ADDRESS:
    raise ValueError("Missing required environment variables (EVM_ADDRESS, AVM_ADDRESS)")


def get_dynamic_price(context: HTTPRequestContext) -> str:
    """Get dynamic price based on tier query parameter."""
    tier = context.adapter.get_query_param("tier") or "standard"
    return "$0.005" if tier == "premium" else "$0.001"


class WeatherReport(BaseModel):
    weather: str
    temperature: int


class WeatherResponse(BaseModel):
    report: WeatherReport


app = FastAPI()

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register(AVM_NETWORK, ExactAvmServerScheme())
server.register(EVM_NETWORK, ExactEvmServerScheme())


# Register hooks to log selected payment option
async def after_verify(ctx):
    print("\n=== Dynamic Price - After verify ===")
    print(f"Amount: {ctx.requirements.amount}")
    print(f"Payer: {ctx.result.payer}")


server.on_after_verify(after_verify)

dynamic_price_accepts = [
    PaymentOption(
        scheme="exact",
        pay_to=AVM_ADDRESS,
        price=get_dynamic_price,
        network=AVM_NETWORK,
    ),
    PaymentOption(
        scheme="exact",
        pay_to=EVM_ADDRESS,
        price=get_dynamic_price,
        network=EVM_NETWORK,
    ),
]

routes = {
    "GET /weather": RouteConfig(
        accepts=dynamic_price_accepts,
    ),
}
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


@app.get("/weather")
async def get_weather(city: str = "San Francisco", tier: str = "standard") -> WeatherResponse:
    return WeatherResponse(report=WeatherReport(weather="sunny", temperature=70))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4021)
