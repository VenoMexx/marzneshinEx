import logging

from app.db import GetDB
from app.db.models import Settings as DBSettings
from app.models.settings import BackupSettings
from app.utils.backup import BackupManager

logger = logging.getLogger(__name__)


async def create_auto_backup():
    """
    Scheduled task to create automatic backups
    Runs based on the configured interval
    """
    try:
        logger.info("Starting automatic backup task")

        # Get backup settings from database
        with GetDB() as db:
            settings_row = db.query(DBSettings.backup).first()
            if not settings_row or not settings_row[0]:
                logger.warning("Backup settings not found in database, using defaults")
                backup_settings = BackupSettings()
            else:
                backup_settings = BackupSettings.model_validate(settings_row[0])

        # Check if backup is enabled
        if not backup_settings.enabled:
            logger.info("Automatic backup is disabled")
            return

        # Create backup
        backup_manager = BackupManager(backup_settings)
        backup_info = await backup_manager.create_backup()

        if backup_info:
            logger.info(
                f"Automatic backup completed: {backup_info.filename} "
                f"({backup_info.size_bytes} bytes)"
            )

            # Cleanup old backups
            await backup_manager.cleanup_old_backups()
        else:
            logger.error("Automatic backup failed")

    except Exception as e:
        logger.error(f"Automatic backup task error: {e}", exc_info=True)
