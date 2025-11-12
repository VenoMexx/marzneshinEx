from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .base import Base, SessionLocal, engine  # noqa
from .crud import (
    create_admin,
    create_user,
    get_admin,
    get_admins,
    get_jwt_secret_key,
    ensure_node_inbounds,
    get_system_usage,
    get_tls_certificate,
    get_user,
    get_user_by_id,
    get_users,
    get_users_count,
    remove_admin,
    remove_user,
    revoke_user_sub,
    set_owner,
    update_admin,
    update_user,
    update_user_status,
    update_user_sub,
)
from .models import JWT, System, User  # noqa


class GetDB:  # Context Manager
    def __init__(self):
        self.db = None

    def __enter__(self):
        self.db = SessionLocal()
        return self.db

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is not None or isinstance(exc_value, SQLAlchemyError):
                # Rollback on any exception
                if self.db:
                    self.db.rollback()
            # Note: No automatic commit - let the caller control commits
        except Exception:
            # If rollback fails, still try to close
            if self.db:
                try:
                    self.db.rollback()
                except Exception:
                    pass
        finally:
            # Always close and cleanup the session
            if self.db:
                try:
                    self.db.expire_all()  # Expire all objects
                    self.db.close()  # Close the session
                except Exception:
                    pass
                finally:
                    self.db = None  # Clear reference


__all__ = [
    "get_user",
    "get_user_by_id",
    "get_users",
    "get_users_count",
    "create_user",
    "remove_user",
    "update_user",
    "update_user_status",
    "update_user_sub",
    "revoke_user_sub",
    "set_owner",
    "get_system_usage",
    "get_jwt_secret_key",
    "get_tls_certificate",
    "get_admin",
    "create_admin",
    "update_admin",
    "remove_admin",
    "get_admins",
    "GetDB",
    "User",
    "System",
    "JWT",
    "Base",
    "Session",
]
