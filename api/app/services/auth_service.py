"""Authentication business logic (register and login)."""

import logging

from app.dao.user_dao import UserDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import AuthenticationError, ConflictError
from app.models.user import User
from app.schemas.mappers.user_mapper import UserMapper
from app.schemas.requests.user_requests import LoginRequest, RegisterRequest
from app.security.passwords import PasswordService

logger = logging.getLogger(__name__)


class AuthService:
    """Creates accounts and verifies credentials."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        user_dao: UserDao,
        password_service: PasswordService,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._user_dao = user_dao
        self._password_service = password_service

    def register(self, request: RegisterRequest) -> User:
        """Create a new account.

        Raises ConflictError when the (normalized) email is already taken.
        Commits the session on success.
        """
        email = UserMapper.normalize_email(str(request.email))
        existing = self._user_dao.get_by_email(email)
        if existing is not None:
            raise ConflictError("An account with this email already exists.")

        password_hash = self._password_service.hash(request.password)
        user = UserMapper.create_user(
            first_name=request.first_name,
            last_name=request.last_name,
            email_normalized=email,
            password_hash=password_hash,
        )
        self._user_dao.add(user)
        self._unit_of_work.commit()
        logger.info("Registered new account %s", email)
        return user

    def login(self, request: LoginRequest) -> User:
        """Verify credentials and return the account.

        Raises AuthenticationError for unknown emails or wrong passwords
        (the same message is used for both to avoid account enumeration).
        """
        email = UserMapper.normalize_email(str(request.email))
        user = self._user_dao.get_by_email(email)
        if user is None or not self._password_service.verify(request.password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        return user
