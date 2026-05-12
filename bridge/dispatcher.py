from __future__ import annotations

import logging
from typing import Awaitable, Callable, Dict, Any

from bridge.models import JsonRpcRequest, JsonRpcResponse
from bridge.ros2_adapter import Ros2Adapter

logger = logging.getLogger(__name__)

HandlerFunc = Callable[..., Awaitable[Any]]

_ROUTES: Dict[str, HandlerFunc] = {}
_handlers_loaded = False


def register(method: str) -> Callable[[HandlerFunc], HandlerFunc]:
    """装饰器：将函数注册为 JSON-RPC method 处理器。"""
    def decorator(func: HandlerFunc) -> HandlerFunc:
        _ROUTES[method] = func
        return func
    return decorator


def _ensure_handlers_loaded() -> None:
    global _handlers_loaded
    if _handlers_loaded:
        return
    from bridge.handlers import voice, navigation, action, robotinfo, network, motion  # noqa: F401
    _handlers_loaded = True


async def dispatch(req: JsonRpcRequest, adapter: Ros2Adapter, **kwargs: Any) -> JsonRpcResponse:
    _ensure_handlers_loaded()

    handler = _ROUTES.get(req.method)
    if handler is None:
        logger.warning("Method not found: %s", req.method)
        return JsonRpcResponse.method_not_found(req.id, req.method)

    try:
        result = await handler(req.params, adapter, **kwargs)
        return JsonRpcResponse.ok(req.id, result)
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Invalid params for %s: %s", req.method, exc)
        return JsonRpcResponse.invalid_params(req.id, str(exc))
    except Exception as exc:
        logger.exception("Handler error for %s", req.method)
        return JsonRpcResponse.internal_error(req.id, str(exc))
