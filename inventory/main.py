import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from router import router

APP_NAME = os.getenv("APP_NAME", "synapseshop-inventory")
DB_HOST = os.getenv("DB_HOST", "not-set")

app = FastAPI(title=APP_NAME, version="0.1.0")
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME, "db_host": DB_HOST}