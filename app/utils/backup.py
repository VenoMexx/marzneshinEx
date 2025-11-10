import asyncio
import logging
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from app.config.env import DATABASE_URL
from app.models.settings import BackupSettings, BackupInfo, RemoteBackupSettings

logger = logging.getLogger(__name__)


class BackupManager:
    def __init__(self, settings: BackupSettings):
        self.settings = settings
        self.backup_dir = Path(settings.backup_location)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup(self) -> BackupInfo:
        """Create a new backup archive"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"marzneshin_backup_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_filename

            logger.info(f"Creating backup: {backup_filename}")

            # Create temporary directory for backup files
            temp_dir = self.backup_dir / f"temp_{timestamp}"
            temp_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Backup database
                if self.settings.include_database:
                    db_backup_path = await self._backup_database(temp_dir)
                    if not db_backup_path:
                        logger.error("Database backup failed")
                        return None

                # Backup logs
                if self.settings.include_logs:
                    await self._backup_logs(temp_dir)

                # Create tar.gz archive
                with tarfile.open(backup_path, "w:gz") as tar:
                    tar.add(temp_dir, arcname=os.path.basename(temp_dir))

                # Get backup size
                backup_size = backup_path.stat().st_size

                # Upload to remote if configured
                if self.settings.remote_backup:
                    await self._upload_to_remote(backup_path)

                logger.info(f"Backup created successfully: {backup_filename} ({backup_size} bytes)")

                return BackupInfo(
                    filename=backup_filename,
                    created_at=datetime.now(),
                    size_bytes=backup_size,
                    location=str(backup_path),
                    is_remote=self.settings.remote_backup is not None
                )

            finally:
                # Cleanup temp directory
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise

    async def _backup_database(self, temp_dir: Path) -> Path | None:
        """Backup database based on database type"""
        try:
            db_backup_file = temp_dir / "database.sql"

            if "sqlite" in DATABASE_URL.lower():
                # SQLite backup
                db_path = DATABASE_URL.replace("sqlite:///", "")
                if os.path.exists(db_path):
                    shutil.copy2(db_path, temp_dir / "database.db")
                    logger.info("SQLite database backed up")
                    return temp_dir / "database.db"
                else:
                    logger.error(f"SQLite database not found: {db_path}")
                    return None

            elif "postgresql" in DATABASE_URL.lower() or "postgres" in DATABASE_URL.lower():
                # PostgreSQL backup
                # Extract connection details from DATABASE_URL
                # postgresql://user:pass@host:port/dbname
                from urllib.parse import urlparse
                parsed = urlparse(DATABASE_URL)

                pg_dump_cmd = [
                    "pg_dump",
                    "-h", parsed.hostname or "localhost",
                    "-p", str(parsed.port or 5432),
                    "-U", parsed.username,
                    "-d", parsed.path.lstrip("/"),
                    "-f", str(db_backup_file)
                ]

                env = os.environ.copy()
                if parsed.password:
                    env["PGPASSWORD"] = parsed.password

                result = await asyncio.create_subprocess_exec(
                    *pg_dump_cmd,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.wait()

                if result.returncode == 0:
                    logger.info("PostgreSQL database backed up")
                    return db_backup_file
                else:
                    logger.error(f"PostgreSQL backup failed: {stderr.decode()}")
                    return None

            elif "mysql" in DATABASE_URL.lower():
                # MySQL backup
                from urllib.parse import urlparse
                parsed = urlparse(DATABASE_URL)

                mysqldump_cmd = [
                    "mysqldump",
                    "-h", parsed.hostname or "localhost",
                    "-P", str(parsed.port or 3306),
                    "-u", parsed.username,
                    f"-p{parsed.password}" if parsed.password else "",
                    parsed.path.lstrip("/"),
                    "--result-file", str(db_backup_file)
                ]

                result = await asyncio.create_subprocess_exec(
                    *mysqldump_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.wait()

                if result.returncode == 0:
                    logger.info("MySQL database backed up")
                    return db_backup_file
                else:
                    logger.error(f"MySQL backup failed: {stderr.decode()}")
                    return None

            else:
                logger.warning(f"Unknown database type in URL: {DATABASE_URL}")
                return None

        except Exception as e:
            logger.error(f"Database backup error: {e}")
            return None

    async def _backup_logs(self, temp_dir: Path):
        """Backup log files"""
        logs_dir = Path("/var/log/marzneshin")
        if logs_dir.exists():
            logs_backup_dir = temp_dir / "logs"
            logs_backup_dir.mkdir(parents=True, exist_ok=True)

            for log_file in logs_dir.glob("*.log"):
                shutil.copy2(log_file, logs_backup_dir)

            logger.info("Logs backed up")

    async def _upload_to_remote(self, backup_path: Path):
        """Upload backup to remote storage"""
        try:
            remote_settings = self.settings.remote_backup
            if not remote_settings:
                return

            if remote_settings.provider == "s3":
                await self._upload_to_s3(backup_path, remote_settings)
            elif remote_settings.provider == "ftp":
                await self._upload_to_ftp(backup_path, remote_settings)
            elif remote_settings.provider == "sftp":
                await self._upload_to_sftp(backup_path, remote_settings)

            logger.info(f"Backup uploaded to {remote_settings.provider}")

        except Exception as e:
            logger.error(f"Remote upload failed: {e}")
            # Don't raise - local backup still exists

    async def _upload_to_s3(self, backup_path: Path, settings: RemoteBackupSettings):
        """Upload to S3-compatible storage"""
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3_client = boto3.client(
                's3',
                endpoint_url=settings.endpoint,
                aws_access_key_id=settings.access_key,
                aws_secret_access_key=settings.secret_key
            )

            remote_path = f"{settings.path}/{backup_path.name}"
            s3_client.upload_file(str(backup_path), settings.bucket, remote_path)
            logger.info(f"Uploaded to S3: {remote_path}")

        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            raise

    async def _upload_to_ftp(self, backup_path: Path, settings: RemoteBackupSettings):
        """Upload to FTP server"""
        # Implementation for FTP upload
        logger.warning("FTP upload not yet implemented")

    async def _upload_to_sftp(self, backup_path: Path, settings: RemoteBackupSettings):
        """Upload to SFTP server"""
        # Implementation for SFTP upload
        logger.warning("SFTP upload not yet implemented")

    async def list_backups(self) -> List[BackupInfo]:
        """List all available backups"""
        backups = []

        if not self.backup_dir.exists():
            return backups

        for backup_file in sorted(self.backup_dir.glob("marzneshin_backup_*.tar.gz"), reverse=True):
            stat = backup_file.stat()
            backups.append(BackupInfo(
                filename=backup_file.name,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                size_bytes=stat.st_size,
                location=str(backup_file),
                is_remote=False
            ))

        return backups

    async def delete_backup(self, filename: str) -> bool:
        """Delete a specific backup"""
        try:
            backup_path = self.backup_dir / filename
            if backup_path.exists() and backup_path.is_file():
                backup_path.unlink()
                logger.info(f"Deleted backup: {filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete backup {filename}: {e}")
            return False

    async def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.settings.retention_days)
            deleted_count = 0

            for backup_file in self.backup_dir.glob("marzneshin_backup_*.tar.gz"):
                stat = backup_file.stat()
                if datetime.fromtimestamp(stat.st_ctime) < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup_file.name}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old backup(s)")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    async def restore_backup(self, filename: str) -> bool:
        """Restore from a backup file"""
        try:
            backup_path = self.backup_dir / filename
            if not backup_path.exists():
                logger.error(f"Backup file not found: {filename}")
                return False

            logger.info(f"Restoring from backup: {filename}")

            # Extract backup
            temp_restore_dir = self.backup_dir / f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_restore_dir.mkdir(parents=True, exist_ok=True)

            try:
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(temp_restore_dir)

                # Find the extracted directory
                extracted_dirs = list(temp_restore_dir.iterdir())
                if not extracted_dirs:
                    logger.error("No files extracted from backup")
                    return False

                restore_dir = extracted_dirs[0]

                # Restore database
                db_file = restore_dir / "database.db"
                sql_file = restore_dir / "database.sql"

                if db_file.exists():
                    # SQLite restore
                    db_path = DATABASE_URL.replace("sqlite:///", "")
                    shutil.copy2(db_file, db_path)
                    logger.info("SQLite database restored")
                elif sql_file.exists():
                    # PostgreSQL/MySQL restore
                    logger.warning("SQL restore requires manual intervention")
                    # Automatic SQL restore would be complex and risky
                    return False

                logger.info(f"Backup restored successfully from: {filename}")
                return True

            finally:
                # Cleanup temp restore directory
                if temp_restore_dir.exists():
                    shutil.rmtree(temp_restore_dir)

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
