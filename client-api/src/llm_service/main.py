from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import uvicorn

from .config import settings
from .api.routes import router as api_router
from .llm.client import LLMClient
from .services.orchestrator import Orchestrator
from .llm.infrastructure.orders_client import OrdersClient

# Application factory to keep things testable
def create_app(logger: logging.Logger) -> FastAPI:

    # Define lifespan before creating the app
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # instantiate shared clients/services and attach to app.state
        app.state.llm_client = LLMClient(settings=settings)
        app.state.orchestrator = Orchestrator(
            llm_client=app.state.llm_client,
            settings=settings,
            logger=logger,
        )
        app.state.orders_client = OrdersClient()

        # Startup
        logger.info("Starting LLM service")
        await app.state.llm_client.startup()
        # Startup main orchestrator
        await app.state.orchestrator.startup()
        # Startup orders storage orchestrator
        await app.state.orders_client.startup()

        yield 

        # Shutdown
        logger.info("Shutting down LLM service")
        await app.state.orchestrator.shutdown()
        await app.state.llm_client.shutdown()
        await app.state.orders_client.shutdown()

    # create the app with lifespan
    app = FastAPI(title="LLM Service", version="0.1.0", lifespan=lifespan)

    app.state.logger = logger
    app.state.settings = settings

    # CORS - adapt origins as needed for dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # include API routes (depends can pull app.state)
    app.include_router(api_router, prefix="/api/v1")

    # global error handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.debug("validation error: %s", exc)
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    return app

# Setup logging first
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("llm_service")

app = create_app(logger=logger)

# If run directly: uvicorn src.llm_service.main:app --reload
if __name__ == "__main__":
    uvicorn.run("src.llm_service.main:app", port=settings.port, reload=True)
