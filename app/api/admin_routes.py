from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.crypto import apply_user_password, user_password_for_display, verify_password
from app.schemas import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    LoginRequest,
    StatsResponse,
    TokenResponse,
    UserMeResponse,
)
from app.database import get_db
from app.deps import require_admin
from app.models import AuditLog, FollowEvent, JoinEvent, MonitorTask, SignApiKey, TelegramBot, User
from app.monitor.manager import get_monitor_manager

from app.services import count_user_tasks, user_me_payload

router = APIRouter(prefix="/admin/api", tags=["admin"])


@router.post("/auth/login", response_model=TokenResponse)
def admin_login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or user.role != "admin" or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token, role=user.role, email=user.email)


@router.get("/me", response_model=UserMeResponse)
def admin_me(user: User = Depends(require_admin), db: Session = Depends(get_db)) -> UserMeResponse:
    return UserMeResponse(**user_me_payload(db, user))


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminUserResponse]:
    users = db.scalars(select(User).order_by(User.id)).all()
    result: list[AdminUserResponse] = []
    for user in users:
        result.append(
            AdminUserResponse(
                id=user.id,
                email=user.email,
                password_plain=user_password_for_display(user),
                role=user.role,
                status=user.status,
                max_monitors=user.max_monitors,
                max_bots=user.max_bots,
                max_groups=user.max_groups,
                monitor_count=count_user_tasks(db, user.id),
                created_at=user.created_at,
            )
        )
    return result


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: AdminUserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    exists = db.scalar(select(User).where(User.email == body.email))
    if exists:
        raise HTTPException(status_code=400, detail="邮箱已存在")

    user = User(
        email=body.email,
        role=body.role,
        max_monitors=body.max_monitors,
        max_bots=body.max_bots,
        max_groups=body.max_groups,
    )
    apply_user_password(user, body.password)
    db.add(user)
    db.flush()
    db.add(
        AuditLog(
            admin_id=admin.id,
            action="create_user",
            target_user_id=user.id,
            detail=f"email={body.email}, role={body.role}",
        )
    )
    db.commit()
    db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        password_plain=user_password_for_display(user),
        role=user.role,
        status=user.status,
        max_monitors=user.max_monitors,
        max_bots=user.max_bots,
        max_groups=user.max_groups,
        monitor_count=0,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    changes: list[str] = []
    if body.status is not None:
        user.status = body.status
        changes.append(f"status={body.status}")
    if body.role is not None:
        user.role = body.role
        changes.append(f"role={body.role}")
    if body.max_monitors is not None:
        user.max_monitors = body.max_monitors
        changes.append(f"max_monitors={body.max_monitors}")
    if body.max_bots is not None:
        user.max_bots = body.max_bots
        changes.append(f"max_bots={body.max_bots}")
    if body.max_groups is not None:
        user.max_groups = body.max_groups
        changes.append(f"max_groups={body.max_groups}")
    if body.password:
        apply_user_password(user, body.password)
        changes.append("password=updated")

    db.add(
        AuditLog(
            admin_id=admin.id,
            action="update_user",
            target_user_id=user.id,
            detail=", ".join(changes) or "no-op",
        )
    )
    db.commit()
    db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        password_plain=user_password_for_display(user),
        role=user.role,
        status=user.status,
        max_monitors=user.max_monitors,
        max_bots=user.max_bots,
        max_groups=user.max_groups,
        monitor_count=count_user_tasks(db, user.id),
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员账号")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        admin_count = db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.id != user_id)
        ) or 0
        if admin_count == 0:
            raise HTTPException(status_code=400, detail="不能删除最后一个管理员")
    db.add(
        AuditLog(
            admin_id=admin.id,
            action="delete_user",
            target_user_id=user.id,
            detail=f"email={user.email}",
        )
    )
    db.delete(user)
    db.commit()
    get_monitor_manager().request_sync()


from app.api.admin_manage import router as manage_router  # noqa: E402

router.include_router(manage_router)


@router.get("/stats", response_model=StatsResponse)
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> StatsResponse:
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    total_task_count = db.scalar(select(func.count()).select_from(MonitorTask)) or 0
    active_task_count = db.scalar(
        select(func.count())
        .select_from(MonitorTask)
        .where(MonitorTask.enabled.is_(True))
    ) or 0
    follow_total = db.scalar(select(func.count()).select_from(FollowEvent)) or 0
    follow_today = db.scalar(
        select(func.count()).select_from(FollowEvent).where(FollowEvent.detected_at >= today)
    ) or 0
    join_total = db.scalar(select(func.count()).select_from(JoinEvent)) or 0
    join_today = db.scalar(
        select(func.count()).select_from(JoinEvent).where(JoinEvent.detected_at >= today)
    ) or 0
    sign_key_count = db.scalar(select(func.count()).select_from(SignApiKey)) or 0
    bot_count = db.scalar(select(func.count()).select_from(TelegramBot)) or 0
    return StatsResponse(
        user_count=user_count,
        active_task_count=active_task_count,
        total_task_count=total_task_count,
        follow_today=follow_today,
        follow_total=follow_total,
        join_today=join_today,
        join_total=join_total,
        sign_key_count=sign_key_count,
        bot_count=bot_count,
    )
