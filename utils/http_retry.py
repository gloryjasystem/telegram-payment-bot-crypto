"""
HTTP retry утилита для внешних API запросов.
Автоматически повторяет при timeout / 5xx / ClientError.
"""
import asyncio
from typing import Optional, Dict, Any

import aiohttp

from utils.logger import bot_logger


async def api_request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    data: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    HTTP-запрос с автоматическим retry при timeout/5xx.
    
    Args:
        method: "GET" или "POST"
        url: URL для запроса
        max_retries: Макс. кол-во повторов (по умолчанию 2)
        retry_delay: Задержка между retry (секунды)
        timeout: Таймаут запроса (секунды)
        headers: Заголовки
        json_data: JSON тело (для POST)
        data: Строковое тело (для POST)
        params: Query параметры (для GET)
    
    Returns:
        dict: {'status': int, 'body': str, 'json': dict|None, 'success': bool}
    
    Raises:
        aiohttp.ClientError: Если все попытки исчерпаны
    """
    last_error = None
    
    for attempt in range(1 + max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {
                    'timeout': aiohttp.ClientTimeout(total=timeout),
                }
                if headers:
                    kwargs['headers'] = headers
                if json_data is not None:
                    kwargs['json'] = json_data
                if data is not None:
                    kwargs['data'] = data
                if params is not None:
                    kwargs['params'] = params
                
                async with session.request(method, url, **kwargs) as resp:
                    body = await resp.text()
                    
                    # 5xx — серверная ошибка → retry
                    if resp.status >= 500:
                        last_error = f"HTTP {resp.status}: {body[:200]}"
                        if attempt < max_retries:
                            bot_logger.warning(
                                f"🔄 Retry {attempt + 1}/{max_retries} for {method} {url} "
                                f"(got {resp.status})"
                            )
                            await asyncio.sleep(retry_delay)
                            continue
                    
                    # Пытаемся распарсить JSON
                    json_result = None
                    try:
                        import json
                        json_result = json.loads(body)
                    except (ValueError, Exception):
                        pass
                    
                    return {
                        'status': resp.status,
                        'body': body,
                        'json': json_result,
                        'success': resp.status < 400,
                    }
        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = str(e)
            if attempt < max_retries:
                bot_logger.warning(
                    f"🔄 Retry {attempt + 1}/{max_retries} for {method} {url} "
                    f"({type(e).__name__}: {e})"
                )
                await asyncio.sleep(retry_delay)
            else:
                bot_logger.error(
                    f"❌ All {max_retries + 1} attempts failed for {method} {url}: {e}"
                )
                raise
    
    # Все retry исчерпаны и был 5xx
    raise aiohttp.ClientResponseError(
        request_info=None,
        history=None,
        status=500,
        message=f"All retries exhausted. Last error: {last_error}",
    )
