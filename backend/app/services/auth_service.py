from app.models import Account
from sqlalchemy.ext.asyncio import AsyncSession

class AuthService:

    async def password_login(
        self,
        email: str,
        password: str,
        db: AsyncSession
    ) -> Account:
        account = await db.execute(select(Account).where(Account.email == email))
        account = account.scalar_one_or_none()
        if not account:
            raise FailException("账号不存在或者密码错误，请核实后重试")
        return account