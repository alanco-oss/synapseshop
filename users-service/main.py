import os

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from rate_limiter import limiter
from routers import users_router, auth_router

APP_NAME = os.getenv("APP_NAME", "synapseshop-users")

app = FastAPI(title=APP_NAME, version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(auth_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}



