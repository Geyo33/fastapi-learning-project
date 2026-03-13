from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes.orders import router as issues_router
from app.routes.restaurants import router as restaurants_router
from app.sql_requests.requests import init_db
from app.middleware.timer import timing_middleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="SQL Storage", lifespan=lifespan)

app.middleware("http")(timing_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

app.include_router(issues_router)
app.include_router(restaurants_router)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8002)