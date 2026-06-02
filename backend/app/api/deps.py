import select
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from config import get_db
from models import Account
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
import jwt
from minio import Minio
from config import settings
from config import get_minio_client
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)
SessionDB = Annotated[AsyncSession, Depends(get_db)]
MinioClient = Annotated[Minio, Depends(get_minio_client)]



async def get_current_user(db: SessionDB, token: Annotated[str, Depends(reusable_oauth2)]) -> Account:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            settings.ALGORITHM
        )
        account_id = payload.get("sub")
        account = await db.execute(select(Account).where(Account.id == account_id)).scalar_one_or_none()
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

CurrentUser = Annotated[Account, Depends(get_current_user)]