from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth.auth_router import router as user_router
from app.api.farm.farm_router import router as farm_router
from app.api.batch.batch_router import router as batch_router
from app.api.cattle.cattle_router import router as cattle_router
from app.api.investment.investment_router import router as investment_router
from app.core.config import CORS_ORIGINS, ENVIRONMENT
from app.core.database import Base, SessionLocal, engine, ensure_schema
from app.models import userModel as _user_model
from app.models import farmModel as _farm_model
from app.models import batchModel as _batch_model
from app.models import cattleModel as _cattle_model
from app.models import investmentBatchModel as _investment_batch_model
from app.seed.seed_service import seed_roles


def _load_models() -> None:
    _ = (
        _user_model.Role,
        _user_model.User,
        _farm_model.Farm,
        _batch_model.Batch,
        _cattle_model.Cattle,
        _cattle_model.CattleWeightLog,
        _investment_batch_model.InvestmentBatch,
    )


_load_models()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    if ENVIRONMENT == "development":
        with SessionLocal() as db:
            seed_roles(db)
    yield


app = FastAPI(
    title="Hatofi API",
    description="API for Hatofi application",
    version="0.0.1",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(user_router)
app.include_router(farm_router)
app.include_router(batch_router)
app.include_router(cattle_router)
app.include_router(investment_router)
