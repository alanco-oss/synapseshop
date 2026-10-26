import os

from fastapi import FastAPI
from rate_limiter import limiter
from routers import auth_router, users_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

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



