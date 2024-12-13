# main.py

import asyncio
import httpx
import json
import uvicorn
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from logger import log
from http_client_manager import client_manager


app = FastAPI(title="HTTP Ретранслятор")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await client_manager.start()
    yield
    await client_manager.dispose_all_clients()


async def make_request_with_retries(client, method, url, headers, params, content):
    """
    Выполняет запрос с повторными попытками при ошибке.
    
    :param client: Экземпляр httpx.AsyncClient
    :param method: HTTP-метод
    :param url: URL целевого запроса
    :param headers: Заголовки запроса
    :param params: Параметры запроса
    :param content: Тело запроса
    :return: Ответ от целевого сервера
    """
    
    http_client = await client_manager.get_client()
    for attempt in range(settings.requests.max_retries):
        try:
            response = await http_client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                content=content,
                follow_redirects=True,
                timeout=settings.requests.timeout,
            )
            return response
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            log.error(f"Retry {attempt + 1} of {settings.requests.max_retries} failed: {e}")
            if attempt < settings.requests.max_retries - 1:
                await asyncio.sleep(settings.requests.retry_delay_sec)
            else:
                raise
        finally:
            await client_manager.release_client(http_client)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def relay_request(request: Request, path: str):
    """
    Ретранслирует входящий запрос на целевой URL и возвращает ответ без изменений.
    
    :param request: Входящий HTTP-запрос
    :param path: Путь запроса
    :return: Ответ от целевого сервера
    """
    # Укажите целевой URL для перенаправления
    target_url = settings.requests.url
    
    # Создаём полный URL для перенаправления
    full_target_url = f"{target_url}/{path}"
    
    # Получаем тело запроса
    request_body = await request.body()
    
    # Копируем все заголовки, кроме служебных
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in ["host", "content-length"]
    }
    
    log.info("request_body: %s headers: %s", request_body, headers)
    
    async with httpx.AsyncClient() as client:
        try:
            # Используем функцию с повторными попытками
            response = await make_request_with_retries(
                client=client,
                method=request.method,
                url=full_target_url,
                headers=headers,
                params=request.query_params,
                content=request_body
            )
            
            # Попытка парсинга JSON-ответа
            try:
                log.info("------------------- JSON Response -------------------")
                response_json = response.json()
                log.info("response_json: %s", response_json)

                new_headers = {
                    'date': response.headers.get('date'),
                    'content-type': response.headers.get('content-type'),
                    'transfer-encoding': response.headers.get('transfer-encoding'),
                    'connection': response.headers.get('connection'),
                }

                # Возвращаем ответ с корректными заголовками и JSON-телом
                return Response(
                    content=json.dumps(response_json),
                    status_code=response.status_code,
                    headers=new_headers,
                    media_type="application/json"
                )
            except json.JSONDecodeError:  # TODO: Double check
                log.info("------------------- Not JSON Response -------------------")
                log.info("response.content: %s", response.content)

                # Если ответ не в JSON, возвращаем как есть
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=new_headers
                )
        
        except Exception as e:  # httpx.RequestError
            # Обработка ошибок
            raise HTTPException(
                status_code=500,
                detail=f"Error during redirection: {e}"
            )


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=True,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.run.host, port=settings.run.port)
