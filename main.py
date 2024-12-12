from fastapi import FastAPI, Request, HTTPException, Response
import httpx
import uvicorn
import json
import asyncio

app = FastAPI(title="HTTP Ретранслятор")

MAX_RETRIES = 3  # Максимальное количество попыток
RETRY_DELAY = 1  # Задержка между попытками (в секундах)


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
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                content=content,
                follow_redirects=True,
                timeout=30,
            )
            return response
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Попытка {attempt + 1} из {MAX_RETRIES} не удалась: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                raise
            

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def relay_request(request: Request, path: str):
    """
    Ретранслирует входящий запрос на целевой URL и возвращает ответ без изменений.
    
    :param request: Входящий HTTP-запрос
    :param path: Путь запроса
    :return: Ответ от целевого сервера
    """
    # Укажите целевой URL для перенаправления
    target_url = "https://api.openai.com"
    
    # Создаём полный URL для перенаправления
    full_target_url = f"{target_url}/{path}"
    
    # Получаем тело запроса
    request_body = await request.body()
    
    # Копируем все заголовки, кроме служебных
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in ["host", "content-length"]
    }
    
    print("request_body:", request_body, "headers:", headers)
    
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
                print("------------------- Ответ в JSON -------------------")
                response_json = response.json()
                print("response_json:", response_json)

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
            except json.JSONDecodeError:
                print("------------------- Ответ не в JSON -------------------")
                print("response.content:", response.content)

                # Если ответ не в JSON, возвращаем как есть
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
        
        except Exception as e:  # httpx.RequestError
            # Обработка ошибок
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при перенаправлении: {e}"
            )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
