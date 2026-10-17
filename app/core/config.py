import os

from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./hatofi.db",
)
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "development-only-change-this-secret-key",
)
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "240"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").strip().lower()
STELLAR_ENABLED = os.getenv("STELLAR_ENABLED", "false").strip().lower() == "true"
STELLAR_NETWORK = os.getenv("STELLAR_NETWORK", "testnet").strip().lower()
STELLAR_RPC_URL = os.getenv(
    "STELLAR_RPC_URL",
    "https://soroban-testnet.stellar.org",
)
STELLAR_CONTRACT_ID = os.getenv("STELLAR_CONTRACT_ID", "")
STELLAR_TOKEN_ID = os.getenv("STELLAR_TOKEN_ID", "")
STELLAR_ADMIN_SECRET = os.getenv("STELLAR_ADMIN_SECRET", "")
STELLAR_DECIMALS = int(os.getenv("STELLAR_DECIMALS", "7"))


def _get_cors_origins() -> list[str]:
    configured_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    ]


CORS_ORIGINS = _get_cors_origins()