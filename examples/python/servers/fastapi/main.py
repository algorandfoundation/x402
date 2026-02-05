import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI, payment_middleware  # noqa: F401
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.mechanisms.svm.exact import ExactSvmServerScheme
from x402.mechanisms.avm.exact import ExactAvmServerScheme
from x402.mechanisms.avm import ALGORAND_TESTNET_CAIP2, USDC_TESTNET_ASA_ID
from x402.schemas import AssetAmount, Network
from x402.server import x402ResourceServer

load_dotenv()

# Config
EVM_ADDRESS = os.getenv("EVM_ADDRESS")
SVM_ADDRESS = os.getenv("SVM_ADDRESS")
AVM_ADDRESS = os.getenv("AVM_ADDRESS")
EVM_NETWORK: Network = "eip155:84532"  # Base Sepolia
SVM_NETWORK: Network = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"  # Solana Devnet
AVM_NETWORK: Network = ALGORAND_TESTNET_CAIP2  # Algorand Testnet
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")

# At least one address is required
if not EVM_ADDRESS and not SVM_ADDRESS and not AVM_ADDRESS:
    raise ValueError("At least one of EVM_ADDRESS, SVM_ADDRESS, or AVM_ADDRESS required")


# Response schemas
class WeatherReport(BaseModel):
    weather: str
    temperature: int


class WeatherResponse(BaseModel):
    report: WeatherReport


class PremiumContentResponse(BaseModel):
    content: str


# App
app = FastAPI()


# x402 Middleware
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)

# Register payment schemes based on available addresses
if EVM_ADDRESS:
    server.register(EVM_NETWORK, ExactEvmServerScheme())
if SVM_ADDRESS:
    server.register(SVM_NETWORK, ExactSvmServerScheme())
if AVM_ADDRESS:
    server.register(AVM_NETWORK, ExactAvmServerScheme())

# Build payment options based on configured addresses
weather_accepts = []
premium_accepts = []

if EVM_ADDRESS:
    weather_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=EVM_ADDRESS,
            price="$0.01",
            network=EVM_NETWORK,
        )
    )
    premium_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=EVM_ADDRESS,
            price=AssetAmount(
                amount="10000",  # $0.01 USDC
                asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
                extra={"name": "USDC", "version": "2"},
            ),
            network=EVM_NETWORK,
        )
    )

if SVM_ADDRESS:
    weather_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=SVM_ADDRESS,
            price="$0.01",
            network=SVM_NETWORK,
        )
    )
    premium_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=SVM_ADDRESS,
            price="$0.01",
            network=SVM_NETWORK,
        )
    )

if AVM_ADDRESS:
    weather_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=AVM_ADDRESS,
            price="$0.01",
            network=AVM_NETWORK,
        )
    )
    premium_accepts.append(
        PaymentOption(
            scheme="exact",
            pay_to=AVM_ADDRESS,
            price=AssetAmount(
                amount="10000",  # $0.01 USDC (6 decimals)
                asset=str(USDC_TESTNET_ASA_ID),
                extra={"name": "USDC", "decimals": 6},
            ),
            network=AVM_NETWORK,
        )
    )

routes = {
    "GET /weather": RouteConfig(
        accepts=weather_accepts,
        mime_type="application/json",
        description="Weather report",
    ),
    "GET /premium/*": RouteConfig(
        accepts=premium_accepts,
        mime_type="application/json",
        description="Premium content",
    ),
}
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
# app.middleware("http")(payment_middleware(routes=routes, server=server))  # Alternative way to register the middleware


# Routes
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/weather")
async def get_weather() -> WeatherResponse:
    return WeatherResponse(report=WeatherReport(weather="sunny", temperature=70))


@app.get("/premium/content")
async def get_premium_content() -> PremiumContentResponse:
    return PremiumContentResponse(content="This is premium content")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4021)
