from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import AsyncMongoClient

from crosfit_training_backend.api.error_handlers import register_error_handlers
from crosfit_training_backend.api.routes.complexes import router as complexes_router
from crosfit_training_backend.api.routes.exercises import router as exercises_router
from crosfit_training_backend.api.routes.me import router as me_router
from crosfit_training_backend.api.routes.stats import router as stats_router
from crosfit_training_backend.api.routes.trainings import router as trainings_router
from crosfit_training_backend.database import init_db
from crosfit_training_backend.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = AsyncMongoClient(settings.MONGO_URL, uuidRepresentation="standard")
    await init_db(client, settings.MONGO_DB_NAME)
    yield
    await client.close()


app = FastAPI(title="Crossfit Training API", lifespan=lifespan)
register_error_handlers(app)
# The frontend runs on another origin. Authentication is a Bearer header, not a
# cookie, so credentials are not needed (and `allow_origins` can stay an exact list).
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().CORS_ORIGINS),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(me_router)
app.include_router(exercises_router)
app.include_router(complexes_router)
app.include_router(trainings_router)
app.include_router(stats_router)
