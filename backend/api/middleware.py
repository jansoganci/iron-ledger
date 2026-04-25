from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.logger import set_trace_id

_HEADER = "X-Trace-Id"


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get(_HEADER) or str(uuid.uuid4())
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers[_HEADER] = trace_id
        return response
