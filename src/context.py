from fastapi import Request
from contextvars import ContextVar

request_ctx: ContextVar[Request] = ContextVar("request_context")
trans_id_ctx: ContextVar[str] = ContextVar("transaction_id_context")
