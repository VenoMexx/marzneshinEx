"""
Bulk Operations Utilities

This module provides utility functions for performing bulk operations on users.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db import crud
from app.db.models import User
from app.models.bulk_operations import (
    BulkOperationType,
    BulkOperationResult,
    BulkOperationResponse,
)

logger = logging.getLogger(__name__)


def perform_bulk_delete(db: Session, usernames: list[str]) -> list[BulkOperationResult]:
    """
    Delete multiple users

    Args:
        db: Database session
        usernames: List of usernames to delete

    Returns:
        List of operation results
    """
    results = []

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            # Start nested transaction for this user
            savepoint = db.begin_nested()
            try:
                crud.remove_user(db, user)
                db.commit()  # Commit this user's transaction

                results.append(BulkOperationResult(
                    username=username,
                    success=True,
                    message="User deleted successfully"
                ))
                logger.info(f"Bulk operation: User {username} deleted")

            except Exception as inner_e:
                savepoint.rollback()  # Rollback only this user
                raise inner_e

        except Exception as e:
            db.rollback()  # Safety rollback
            logger.error(f"Bulk operation: Failed to delete user {username}: {e}")
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def perform_bulk_activate(db: Session, usernames: list[str]) -> list[BulkOperationResult]:
    """
    Activate multiple users

    Args:
        db: Database session
        usernames: List of usernames to activate

    Returns:
        List of operation results
    """
    results = []

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            if user.enabled and user.activated:
                results.append(BulkOperationResult(
                    username=username,
                    success=True,
                    message="User already active"
                ))
                continue

            user.enabled = True
            user.activated = True
            db.commit()

            results.append(BulkOperationResult(
                username=username,
                success=True,
                message="User activated successfully"
            ))
            logger.info(f"Bulk operation: User {username} activated")

        except Exception as e:
            logger.error(f"Bulk operation: Failed to activate user {username}: {e}")
            db.rollback()
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def perform_bulk_deactivate(db: Session, usernames: list[str]) -> list[BulkOperationResult]:
    """
    Deactivate multiple users

    Args:
        db: Database session
        usernames: List of usernames to deactivate

    Returns:
        List of operation results
    """
    results = []

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            if not user.enabled:
                results.append(BulkOperationResult(
                    username=username,
                    success=True,
                    message="User already inactive"
                ))
                continue

            user.enabled = False
            db.commit()

            results.append(BulkOperationResult(
                username=username,
                success=True,
                message="User deactivated successfully"
            ))
            logger.info(f"Bulk operation: User {username} deactivated")

        except Exception as e:
            logger.error(f"Bulk operation: Failed to deactivate user {username}: {e}")
            db.rollback()
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def perform_bulk_reset_traffic(db: Session, usernames: list[str]) -> list[BulkOperationResult]:
    """
    Reset traffic for multiple users

    Args:
        db: Database session
        usernames: List of usernames to reset traffic

    Returns:
        List of operation results
    """
    results = []

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            old_traffic = user.used_traffic
            user.used_traffic = 0
            user.traffic_reset_at = datetime.utcnow()
            db.commit()

            results.append(BulkOperationResult(
                username=username,
                success=True,
                message=f"Traffic reset (was {old_traffic} bytes)"
            ))
            logger.info(f"Bulk operation: User {username} traffic reset from {old_traffic} to 0")

        except Exception as e:
            logger.error(f"Bulk operation: Failed to reset traffic for user {username}: {e}")
            db.rollback()
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def perform_bulk_reset_days(db: Session, usernames: list[str], days: int) -> list[BulkOperationResult]:
    """
    Reset expiry date to N days from now for multiple users

    Args:
        db: Database session
        usernames: List of usernames
        days: Number of days from now

    Returns:
        List of operation results
    """
    results = []
    new_expire_date = datetime.utcnow() + timedelta(days=days)

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            user.expire_date = new_expire_date
            user.expire_strategy = "fixed_date"
            db.commit()

            results.append(BulkOperationResult(
                username=username,
                success=True,
                message=f"Expiry reset to {days} days from now"
            ))
            logger.info(f"Bulk operation: User {username} expiry reset to {new_expire_date}")

        except Exception as e:
            logger.error(f"Bulk operation: Failed to reset days for user {username}: {e}")
            db.rollback()
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def perform_bulk_extend_days(db: Session, usernames: list[str], days: int) -> list[BulkOperationResult]:
    """
    Extend expiry date by N days for multiple users

    Args:
        db: Database session
        usernames: List of usernames
        days: Number of days to extend

    Returns:
        List of operation results
    """
    results = []

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            if user.expire_date:
                old_date = user.expire_date
                user.expire_date = user.expire_date + timedelta(days=days)
                message = f"Expiry extended from {old_date.date()} to {user.expire_date.date()}"
            else:
                user.expire_date = datetime.utcnow() + timedelta(days=days)
                user.expire_strategy = "fixed_date"
                message = f"Expiry set to {days} days from now"

            db.commit()

            results.append(BulkOperationResult(
                username=username,
                success=True,
                message=message
            ))
            logger.info(f"Bulk operation: User {username} expiry extended by {days} days")

        except Exception as e:
            logger.error(f"Bulk operation: Failed to extend days for user {username}: {e}")
            db.rollback()
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def perform_bulk_add_traffic(db: Session, usernames: list[str], traffic_gb: float) -> list[BulkOperationResult]:
    """
    Add traffic quota (GB) to multiple users

    Args:
        db: Database session
        usernames: List of usernames
        traffic_gb: Traffic to add in GB

    Returns:
        List of operation results
    """
    results = []
    traffic_bytes = int(traffic_gb * 1024 * 1024 * 1024)

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            if user.data_limit is None:
                user.data_limit = traffic_bytes
                message = f"Data limit set to {traffic_gb:.2f} GB"
            else:
                old_limit_gb = user.data_limit / (1024 ** 3)
                user.data_limit += traffic_bytes
                new_limit_gb = user.data_limit / (1024 ** 3)
                message = f"Data limit increased from {old_limit_gb:.2f} GB to {new_limit_gb:.2f} GB"

            db.commit()

            results.append(BulkOperationResult(
                username=username,
                success=True,
                message=message
            ))
            logger.info(f"Bulk operation: User {username} traffic increased by {traffic_gb} GB")

        except Exception as e:
            logger.error(f"Bulk operation: Failed to add traffic for user {username}: {e}")
            db.rollback()
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def perform_bulk_set_traffic_limit(db: Session, usernames: list[str], traffic_gb: float) -> list[BulkOperationResult]:
    """
    Set traffic limit (GB) for multiple users

    Args:
        db: Database session
        usernames: List of usernames
        traffic_gb: Traffic limit in GB

    Returns:
        List of operation results
    """
    results = []
    traffic_bytes = int(traffic_gb * 1024 * 1024 * 1024)

    # Optimize: Fetch all users in one query
    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_dict = {user.username: user for user in users}

    for username in usernames:
        try:
            user = user_dict.get(username)
            if not user:
                results.append(BulkOperationResult(
                    username=username,
                    success=False,
                    error="User not found"
                ))
                continue

            user.data_limit = traffic_bytes
            db.commit()

            results.append(BulkOperationResult(
                username=username,
                success=True,
                message=f"Data limit set to {traffic_gb:.2f} GB"
            ))
            logger.info(f"Bulk operation: User {username} traffic limit set to {traffic_gb} GB")

        except Exception as e:
            logger.error(f"Bulk operation: Failed to set traffic limit for user {username}: {e}")
            db.rollback()
            results.append(BulkOperationResult(
                username=username,
                success=False,
                error=str(e)
            ))

    return results


def execute_bulk_operation(
    db: Session,
    operation: BulkOperationType,
    usernames: list[str],
    days: int | None = None,
    traffic_gb: float | None = None,
) -> BulkOperationResponse:
    """
    Execute bulk operation on users

    Args:
        db: Database session
        operation: Operation type
        usernames: List of usernames
        days: Number of days (for extend/reset days operations)
        traffic_gb: Traffic in GB (for traffic operations)

    Returns:
        Bulk operation response with results

    Raises:
        ValueError: If required parameters are missing for operation type
    """
    # Validate parameters based on operation type
    if operation in [BulkOperationType.EXTEND_DAYS, BulkOperationType.RESET_DAYS]:
        if days is None or days < 1:
            raise ValueError(f"Operation '{operation}' requires 'days' parameter (must be >= 1)")

    if operation in [BulkOperationType.ADD_TRAFFIC, BulkOperationType.SET_TRAFFIC_LIMIT]:
        if traffic_gb is None or traffic_gb < 0:
            raise ValueError(f"Operation '{operation}' requires 'traffic_gb' parameter (must be >= 0)")

    # Execute operation
    if operation == BulkOperationType.DELETE:
        results = perform_bulk_delete(db, usernames)
    elif operation == BulkOperationType.ACTIVATE:
        results = perform_bulk_activate(db, usernames)
    elif operation == BulkOperationType.DEACTIVATE:
        results = perform_bulk_deactivate(db, usernames)
    elif operation == BulkOperationType.RESET_TRAFFIC:
        results = perform_bulk_reset_traffic(db, usernames)
    elif operation == BulkOperationType.RESET_DAYS:
        results = perform_bulk_reset_days(db, usernames, days)
    elif operation == BulkOperationType.EXTEND_DAYS:
        results = perform_bulk_extend_days(db, usernames, days)
    elif operation == BulkOperationType.ADD_TRAFFIC:
        results = perform_bulk_add_traffic(db, usernames, traffic_gb)
    elif operation == BulkOperationType.SET_TRAFFIC_LIMIT:
        results = perform_bulk_set_traffic_limit(db, usernames, traffic_gb)
    else:
        raise ValueError(f"Unknown operation type: {operation}")

    # Calculate statistics
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    return BulkOperationResponse(
        operation=operation,
        total=len(results),
        successful=successful,
        failed=failed,
        results=results,
    )
