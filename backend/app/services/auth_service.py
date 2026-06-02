import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from models import Account
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from typing import Optional
from config import settings
import jwt
from fastapi import HTTPException
from typing import Any
from pwdlib import PasswordHash
from utils import get_client_ip

password_hash = PasswordHash.recommended()
class AuthService:
    """认证服务"""

    @classmethod
    async def password_login(
        cls,
        db: AsyncSession,
        username: str,
        password: str,
        request: Request,
    ) -> dict[str, Any]:
        """根据用户名+密码进行登录"""
        # 1. 根据username查询用户（email字段）
        result = await db.execute(select(Account).where(Account.email == username))
        account = result.scalar_one_or_none()
        # 获取请求IP
        request_ip = get_client_ip(request)
        
        # 2. 用户不存在：创建新用户
        if not account:
            account = Account(
                id=uuid.uuid4(),
                email=username,
                hashed_password=password_hash.hash(password),  # 存储哈希值
                last_login_ip=request_ip,
                last_login_at=datetime.now(timezone.utc),  # 新增用户时也设置登录时间
            )
            db.add(account)  # 新增对象需加入会话
            await db.commit()
            await db.refresh(account)
        
        # 3. 用户存在：验证密码 + 更新登录信息
        else:
            # ✅ 修正：密码验证逻辑（明文密码 + 数据库哈希值）
            if not password_hash.verify(password, account.hashed_password):
                raise HTTPException(status_code=400, detail="账号不存在或者密码错误，请核实后重试")
            
            # ✅ 修正：更新登录信息（关键：修改后需告知会话）
            account.last_login_at = datetime.now(timezone.utc)
            account.last_login_ip = request_ip  # 顺便更新登录IP
            db.add(account)  # 重新加入会话，标记为已修改（异步会话关键步骤）
            await db.commit()
            await db.refresh(account)
        
        # 4. 生成token
        data = {
            "sub": str(account.id),  # 注意：UUID需转字符串，避免JSON序列化问题
            "username": account.email
        }
        access_token_info = await cls.create_access_token(data)
        return access_token_info
        
    @classmethod
    async def create_access_token(
        cls,
        data: dict,
    ) -> dict[str, Any]:
        """创建访问令牌"""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        expire_at = int(expire.timestamp())
        return {
            "access_token": encoded_jwt,
            "expire_at": expire_at,
        }
