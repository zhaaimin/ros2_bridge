from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class JsonRpcRequest:
    method: str
    id: Optional[Any]
    params: dict
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: dict) -> JsonRpcRequest:
        return cls(
            method=data.get("method", ""),
            id=data.get("id"),
            params=data.get("params") or {},
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


@dataclass
class JsonRpcResponse:
    id: Optional[Any]
    result: Any = None
    error: Optional[dict] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict:
        d: dict = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d

    @classmethod
    def ok(cls, req_id: Any, result: Any) -> JsonRpcResponse:
        return cls(id=req_id, result=result)

    @classmethod
    def method_not_found(cls, req_id: Any, method: str) -> JsonRpcResponse:
        return cls(id=req_id, error={"code": -32601, "message": f"Method not found: {method}"})

    @classmethod
    def invalid_params(cls, req_id: Any, detail: str) -> JsonRpcResponse:
        return cls(id=req_id, error={"code": -32602, "message": f"Invalid params: {detail}"})

    @classmethod
    def internal_error(cls, req_id: Any, detail: str) -> JsonRpcResponse:
        return cls(id=req_id, error={"code": -32000, "message": detail})
