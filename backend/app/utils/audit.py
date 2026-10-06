from typing import Any, Optional
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.user import User


async def log_audit_event(
    session: AsyncSession,
    action: str,
    table_name: str,
    user: Optional[User] = None,
    record_id: Optional[int] = None,
    old_data: Optional[Any] = None,
    new_data: Optional[Any] = None,
    request: Optional[Request] = None,
) -> None:
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    audit = AuditLog(
        user_id=user.id if user else None,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(audit)
