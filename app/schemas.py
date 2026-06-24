from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class UserMeResponse(BaseModel):
    id: int
    email: str
    role: str
    max_monitors: int
    max_bots: int
    max_groups: int
    monitor_count: int = 0
    bot_count: int = 0
    group_count: int = 0
    group_binding_count: int = 0


class BotCreate(BaseModel):
    bot_token: str = Field(min_length=10, max_length=256)
    name: Optional[str] = Field(default=None, max_length=100)


class BotPreviewRequest(BaseModel):
    bot_token: str = Field(min_length=10, max_length=256)


class BotPreviewResponse(BaseModel):
    bot_telegram_id: int
    username: str
    display_name: str


class BotResponse(BaseModel):
    id: int
    name: str
    bot_telegram_id: Optional[int]
    username: Optional[str]
    bot_token: str
    is_active: bool
    created_at: datetime


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    chat_id: str = Field(min_length=1, max_length=64)


class GroupResponse(BaseModel):
    id: int
    name: str
    chat_id: str
    bot_id: Optional[int]
    is_active: bool
    created_at: datetime


class DiscoveredGroupResponse(BaseModel):
    chat_id: str
    name: str
    chat_type: str


class GroupBatchImportItem(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)


class GroupBatchImportRequest(BaseModel):
    bot_id: int
    items: List[GroupBatchImportItem] = Field(min_length=1)


class GroupBatchImportResponse(BaseModel):
    imported: int
    skipped: int
    groups: List[GroupResponse]


class GroupRefreshFailure(BaseModel):
    group_id: int
    chat_id: str
    reason: str


class GroupRefreshNamesResponse(BaseModel):
    updated: int
    unchanged: int
    failed: List[GroupRefreshFailure]


class StreamerCreate(BaseModel):
    unique_id: str = Field(min_length=1, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("unique_id")
    @classmethod
    def normalize_unique_id(cls, value: str) -> str:
        return value.strip().lstrip("@")


class StreamerResponse(BaseModel):
    id: int
    unique_id: str
    display_name: Optional[str]
    created_at: datetime


class SignApiKeyCreate(BaseModel):
    sign_api_key: str = Field(min_length=20, max_length=512)
    label: Optional[str] = Field(default=None, max_length=100)

    @field_validator("sign_api_key")
    @classmethod
    def normalize_sign_api_key(cls, value: str) -> str:
        return value.strip()


class SignApiKeyUsage(BaseModel):
    task_id: int
    streamer_unique_id: str


class SignApiKeyResponse(BaseModel):
    id: int
    label: Optional[str]
    sign_api_key: str
    in_use: bool
    usage: Optional[SignApiKeyUsage] = None
    rate_limits: Optional[dict] = None
    rate_limit_checked_at: Optional[datetime] = None
    created_at: datetime


class SignApiKeyBatchCreate(BaseModel):
    sign_api_keys: List[str] = Field(min_length=1, max_length=100)
    label: Optional[str] = Field(default=None, max_length=100)


class SignApiKeyBatchFailure(BaseModel):
    sign_api_key: str
    reason: str


class SignApiKeyBatchResponse(BaseModel):
    imported: int
    failed: List[SignApiKeyBatchFailure]
    keys: List[SignApiKeyResponse]


class TaskCreate(BaseModel):
    streamer_id: int
    sign_api_key_id: Optional[int] = None
    sign_api_key: Optional[str] = Field(default=None, min_length=20, max_length=512)
    follow_bot_id: Optional[int] = None
    follow_group_id: Optional[int] = None
    join_bot_id: Optional[int] = None
    join_group_id: Optional[int] = None
    join_rate_limit_per_minute: int = Field(default=20, ge=0, le=200)
    enabled: bool = True

    @field_validator("sign_api_key")
    @classmethod
    def normalize_sign_api_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip()


class TaskUpdate(BaseModel):
    sign_api_key_id: Optional[int] = None
    sign_api_key: Optional[str] = Field(default=None, min_length=20, max_length=512)
    follow_bot_id: Optional[int] = None
    follow_group_id: Optional[int] = None
    join_bot_id: Optional[int] = None
    join_group_id: Optional[int] = None
    join_rate_limit_per_minute: Optional[int] = Field(default=None, ge=0, le=200)
    enabled: Optional[bool] = None

    @field_validator("sign_api_key")
    @classmethod
    def normalize_sign_api_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip()


class TaskResponse(BaseModel):
    id: int
    enabled: bool
    status: str
    last_error: Optional[str]
    join_rate_limit_per_minute: int
    streamer: StreamerResponse
    follow_bot_id: Optional[int]
    follow_group_id: Optional[int]
    join_bot_id: Optional[int]
    join_group_id: Optional[int]
    sign_api_key_id: Optional[int]
    sign_api_key: Optional[str]
    sign_api_key_hint: Optional[str]
    created_at: datetime


class FollowEventResponse(BaseModel):
    id: int
    streamer_unique_id: str
    follower_unique_id: str
    follower_nickname: str
    detected_at: datetime


class JoinEventResponse(BaseModel):
    id: int
    streamer_unique_id: str
    guest_unique_id: str
    guest_nickname: str
    detected_at: datetime


class EventStatsResponse(BaseModel):
    follow_today: int
    join_today: int
    streamer_unique_id: Optional[str] = None


class UserDashboardStatsResponse(BaseModel):
    active_task_count: int
    inactive_task_count: int
    total_task_count: int
    sign_key_in_use: int
    sign_key_idle: int
    sign_key_total: int
    bot_pushing: int
    bot_idle: int
    bot_total: int
    group_pushing: int
    group_idle: int
    group_total: int
    follow_today: int
    follow_total: int
    join_today: int
    join_total: int


class PaginatedFollowEventsResponse(BaseModel):
    items: List[FollowEventResponse]
    total: int
    page: int
    page_size: int


class PaginatedJoinEventsResponse(BaseModel):
    items: List[JoinEventResponse]
    total: int
    page: int
    page_size: int


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Literal["user", "admin"] = "user"
    max_monitors: int = Field(default=10, ge=1, le=100)
    max_bots: int = Field(default=10, ge=1, le=100)
    max_groups: int = Field(default=10, ge=1, le=100)


class AdminUserUpdate(BaseModel):
    status: Optional[Literal["active", "disabled"]] = None
    role: Optional[Literal["user", "admin"]] = None
    max_monitors: Optional[int] = Field(default=None, ge=1, le=100)
    max_bots: Optional[int] = Field(default=None, ge=1, le=100)
    max_groups: Optional[int] = Field(default=None, ge=1, le=100)
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


class AdminStreamerCreate(BaseModel):
    user_id: int = Field(ge=1)
    unique_id: str = Field(min_length=1, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("unique_id")
    @classmethod
    def normalize_unique_id(cls, value: str) -> str:
        return value.strip().lstrip("@")


class AdminStreamerUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    user_id: Optional[int] = Field(default=None, ge=1)


class AdminStreamerResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    unique_id: str
    display_name: Optional[str]
    task_count: int
    enabled_task_count: int
    created_at: datetime


class AdminSignKeyCreate(BaseModel):
    user_id: int = Field(ge=1)
    sign_api_key: str = Field(min_length=20, max_length=512)
    label: Optional[str] = Field(default=None, max_length=100)

    @field_validator("sign_api_key")
    @classmethod
    def normalize_sign_api_key(cls, value: str) -> str:
        return value.strip()


class AdminSignKeyUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=100)
    user_id: Optional[int] = Field(default=None, ge=1)


class AdminSignKeyUsage(BaseModel):
    task_id: int
    streamer_unique_id: str


class AdminSignKeyResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    label: Optional[str]
    sign_api_key: str
    in_use: bool
    usage: Optional[AdminSignKeyUsage] = None
    rate_limits: Optional[dict] = None
    rate_limit_checked_at: Optional[datetime] = None
    created_at: datetime


class AdminBotCreate(BaseModel):
    user_id: int = Field(ge=1)
    bot_token: str = Field(min_length=10, max_length=256)
    name: Optional[str] = Field(default=None, max_length=100)


class AdminBotUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    bot_token: Optional[str] = Field(default=None, min_length=10, max_length=256)
    is_active: Optional[bool] = None
    user_id: Optional[int] = Field(default=None, ge=1)


class AdminBotResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    name: str
    bot_telegram_id: Optional[int]
    username: Optional[str]
    bot_token: str
    is_active: bool
    created_at: datetime


class AdminUserOption(BaseModel):
    id: int
    email: str
    role: str
    status: str


class AdminUserResponse(BaseModel):
    id: int
    email: str
    password_plain: Optional[str] = None
    role: str
    status: str
    max_monitors: int
    max_bots: int
    max_groups: int
    monitor_count: int
    created_at: datetime


class AdminGroupCreate(BaseModel):
    user_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=100)
    chat_id: str = Field(min_length=1, max_length=64)
    bot_id: Optional[int] = Field(default=None, ge=1)
    is_active: bool = True


class AdminGroupUpdate(BaseModel):
    user_id: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    chat_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    bot_id: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None


class AdminGroupResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    bot_id: Optional[int]
    bot_name: Optional[str]
    name: str
    chat_id: str
    is_active: bool
    created_at: datetime


class StatsResponse(BaseModel):
    user_count: int
    active_task_count: int
    total_task_count: int
    follow_today: int
    follow_total: int
    join_today: int
    join_total: int
    sign_key_count: int
    bot_count: int
