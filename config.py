# config.py
import os

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from dotenv import load_dotenv


load_dotenv(".env")


RUN_HOST = os.getenv("RUN_HOST", "0.0.0.0")
RUN_PORT = int(os.getenv("RUN_PORT", 8000))
RUN_WORKERS = int(os.getenv("RUN_WORKERS", 2))
RUN_TIMEOUT = int(os.getenv("RUN_TIMEOUT", 30))
DEBUG = os.getenv("DEBUG", "True")

REQUESTS_URL = os.getenv("REQUESTS_URL", "https://api.openai.com")
REQUESTS_MAX_RETRIES = int(os.getenv("REQUESTS_MAX_RETRIES", 3))
REQUESTS_RETRY_DELAY_SEC = int(os.getenv("REQUESTS_RETRY_DELAY_SEC", 1))
REQUESTS_TIMEOUT = int(os.getenv("REQUESTS_TIMEOUT", 30))

CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", ["*"])
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", ["*"])
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", ["*"])

HTTP_CLIENT_TIMEOUT = int(os.getenv("HTTP_CLIENT_TIMEOUT", "300"))
HTTP_CLIENTS_MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("HTTP_CLIENTS_MAX_KEEPALIVE_CONNECTIONS", "10"))


class RunConfig(BaseModel):
    host: str = RUN_HOST
    port: int = RUN_PORT
    workers: int = RUN_WORKERS
    timeout: int = RUN_TIMEOUT
    debug: bool = DEBUG


class RequestsConfig(BaseModel):
    url: str = REQUESTS_URL
    max_retries: int = REQUESTS_MAX_RETRIES
    retry_delay_sec: int = REQUESTS_RETRY_DELAY_SEC
    timeout: int = REQUESTS_TIMEOUT


class CORSConfig(BaseModel):
    allow_origins: list[str] = CORS_ALLOW_ORIGINS
    allow_methods: list[str] = CORS_ALLOW_METHODS
    allow_headers: list[str] = CORS_ALLOW_HEADERS


class HTTPClientConfig(BaseModel):
    timeout: int = HTTP_CLIENT_TIMEOUT
    max_keepalive_connections: int = HTTP_CLIENTS_MAX_KEEPALIVE_CONNECTIONS


class Settings(BaseSettings):
    run: RunConfig = RunConfig()
    requests: RequestsConfig = RequestsConfig()
    cors: CORSConfig = CORSConfig()
    http_client: HTTPClientConfig = HTTPClientConfig()


settings = Settings()
