
from backend.app.models import Account
from backend.app.schemas import AccountInfo
from pwdlib import PasswordHash
password_hash = PasswordHash.recommended()
class AccountService:
    """账号服务"""
    @classmethod
    async def get_account_info(cls, current_user: Account):
        """获取当前登录账号信息"""

        return AccountInfo(
            id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            avatar=current_user.avatar,
            last_login_at=int(current_user.last_login_at.timestamp()),
            last_login_ip=current_user.last_login_ip,
            created_at=int(current_user.created_at.timestamp())
        )
    
    @classmethod
    async def update_password(cls, db: AsyncSession, password: str, account: Account):
        """修改当前登录账号密码"""
        account.hashed_password = password_hash.hash(password)

        # 更新密码
        await db.commit()
        await db.refresh(account)
        return account
    
    @classmethod
    async def update_name(cls, db: AsyncSession, name: str, account: Account):
        """修改当前登录账号名称"""
        account.name = name
        await db.commit()
        await db.refresh(account)
        return account
    
    @classmethod
    async def update_avatar(cls, db: AsyncSession, avatar: str, account: Account):
        """修改当前登录账号头像"""
        account.avatar = avatar
        await db.commit()
        await db.refresh(account)
        return account


        
