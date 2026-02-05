"""Dynamic pay-to routing example."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import HTTPRequestContext, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.mechanisms.avm.exact import ExactAvmServerScheme
from x402.mechanisms.avm import ALGORAND_TESTNET_CAIP2
from x402.schemas import Network
from x402.server import x402ResourceServer

load_dotenv()

# Config
EVM_ADDRESS = os.getenv("EVM_ADDRESS")
AVM_ADDRESS = os.getenv("AVM_ADDRESS")
EVM_NETWORK: Network = "eip155:84532"  # Base Sepolia
AVM_NETWORK: Network = ALGORAND_TESTNET_CAIP2  # Algorand Testnet
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")

if not EVM_ADDRESS and not AVM_ADDRESS:
    raise ValueError("At least one of EVM_ADDRESS or AVM_ADDRESS is required")

# Address lookup for dynamic pay-to (EVM)
EVM_ADDRESS_LOOKUP: dict[str, str] = {
    "US": EVM_ADDRESS or "",
    "UK": EVM_ADDRESS or "",
    "CA": EVM_ADDRESS or "",
    "AU": EVM_ADDRESS or "",
}

# Address lookup for dynamic pay-to (AVM)
AVM_ADDRESS_LOOKUP: dict[str, str] = {
    "US": AVM_ADDRESS or "",
    "UK": AVM_ADDRESS or "",
    "CA": AVM_ADDRESS or "",
    "AU": AVM_ADDRESS or "",
}


def get_dynamic_evm_pay_to(context: HTTPRequestContext) -> str:
    """Get dynamic EVM pay-to address based on country query parameter."""
    country = context.adapter.get_query_param("country") or "US"
    return EVM_ADDRESS_LOOKUP.get(country, EVM_ADDRESS or "")


def get_dynamic_avm_pay_to(context: HTTPRequestContext) -> str:
    """Get dynamic AVM pay-to address based on country query parameter."""
    country = context.adapter.get_query_param("country") or "US"
    return AVM_ADDRESS_LOOKUP.get(country, AVM_ADDRESS or "")


class WeatherReport(BaseModel):
    weather: str
    temperature: int


class WeatherResponse(BaseModel):
    report: WeatherReport


app = FastAPI()

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
if EVM_ADDRESS:
    server.register(EVM_NETWORK, ExactEvmServerScheme())
if AVM_ADDRESS:
    server.register(AVM_NETWORK, ExactAvmServerScheme())


# Register hooks to log selected payment option
async def after_verify(ctx):
    print("\n=== Dynamic Pay-To - After verify ===")
    print(f"Pay to: {ctx.requirements.pay_to}")
    print(f"Payer: {ctx.result.payer}")


server.on_after_verify(after_verify)

# Build accepts list based on available addresses
dynamic_pay_to_accepts = []
if EVM_ADDRESS:
    dynamic_pay_to_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=get_dynamic_evm_pay_to,
            price="$0.001",
            network=EVM_NETWORK,
        )
    )
if AVM_ADDRESS:
    dynamic_pay_to_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=get_dynamic_avm_pay_to,
            price="$0.001",
            network=AVM_NETWORK,
        )
    )

routes = {
    "GET /weather": RouteConfig(
        accepts=dynamic_pay_to_accepts,
    ),
}
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


@app.get("/weather")
async def get_weather(city: str = "San Francisco", country: str = "US") -> WeatherResponse:
    return WeatherResponse(report=WeatherReport(weather="sunny", temperature=70))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4021)
