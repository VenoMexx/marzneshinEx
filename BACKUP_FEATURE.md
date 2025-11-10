# Automatic Backup Feature Implementation

## Overview

This document describes the automatic backup feature added to Marzneshin. The feature provides automated backup creation, storage management, and restoration capabilities.

## Backend Implementation

### 1. Models (app/models/settings.py)

**New Models:**
- `BackupSettings`: Configuration for backup behavior
- `RemoteBackupSettings`: S3/FTP/SFTP remote storage configuration
- `BackupInfo`: Backup metadata response model

**Settings Integration:**
```python
class Settings(BaseModel):
    subscription: SubscriptionSettings
    telegram: TelegramSettings | None
    backup: BackupSettings = Field(default_factory=BackupSettings)
```

### 2. Backup Manager (app/utils/backup.py)

**Key Features:**
- Automatic database backup (SQLite, PostgreSQL, MySQL)
- Log file backup (optional)
- Remote storage upload (S3-compatible, FTP, SFTP)
- Automatic cleanup of old backups based on retention policy
- Backup restoration

**Usage:**
```python
from app.utils.backup import BackupManager

backup_manager = BackupManager(backup_settings)
backup_info = await backup_manager.create_backup()
```

### 3. Scheduled Task (app/tasks/backup.py)

**Task:** `create_auto_backup()`
- Runs based on configured interval (default: 6 hours)
- Automatically creates backups
- Cleans up old backups

### 4. API Endpoints (app/routes/system.py)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/settings/backup` | Get backup settings |
| PUT | `/api/system/settings/backup` | Update backup settings |
| GET | `/api/system/backups` | List all backups |
| POST | `/api/system/backups/create` | Create manual backup |
| GET | `/api/system/backups/{filename}/download` | Download backup file |
| DELETE | `/api/system/backups/{filename}` | Delete backup |
| POST | `/api/system/backups/{filename}/restore` | Restore from backup |
| POST | `/api/system/backups/cleanup` | Manually trigger cleanup |

### 5. Configuration

**Environment Variable:**
```bash
TASKS_AUTO_BACKUP_INTERVAL=21600  # 6 hours in seconds
```

**Default Settings:**
```json
{
  "enabled": true,
  "interval_hours": 6,
  "retention_days": 7,
  "backup_location": "/var/lib/marzneshin/backups",
  "include_database": true,
  "include_logs": false,
  "remote_backup": null
}
```

## Frontend Integration (TODO)

### Recommended Structure

```
dashboard/src/modules/settings/backup/
├── backup-settings.tsx       # Backup configuration form
├── backup-list.tsx           # List of available backups
├── backup-actions.tsx        # Create/Restore/Delete actions
└── remote-backup-config.tsx  # Remote storage configuration
```

### API Client Example

```typescript
// dashboard/src/lib/api/backup.ts

export const backupApi = {
  // Get backup settings
  getSettings: () =>
    fetch('/api/system/settings/backup').then(res => res.json()),

  // Update backup settings
  updateSettings: (settings: BackupSettings) =>
    fetch('/api/system/settings/backup', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    }),

  // List backups
  listBackups: () =>
    fetch('/api/system/backups').then(res => res.json()),

  // Create backup
  createBackup: () =>
    fetch('/api/system/backups/create', { method: 'POST' })
      .then(res => res.json()),

  // Download backup
  downloadBackup: (filename: string) =>
    fetch(`/api/system/backups/${filename}/download`)
      .then(res => res.blob()),

  // Delete backup
  deleteBackup: (filename: string) =>
    fetch(`/api/system/backups/${filename}`, { method: 'DELETE' }),

  // Restore backup
  restoreBackup: (filename: string) =>
    fetch(`/api/system/backups/${filename}/restore`, { method: 'POST' })
}
```

### UI Components Structure

**Backup Settings Page:**
- Toggle: Enable/Disable automatic backups
- Number Input: Backup interval (hours)
- Number Input: Retention period (days)
- Text Input: Backup location path
- Checkbox: Include database
- Checkbox: Include logs
- Remote Backup Configuration (collapsible)
  - Select: Provider (S3/FTP/SFTP)
  - Credentials inputs

**Backup List Page:**
- Table with columns:
  - Filename
  - Created At
  - Size
  - Location
  - Actions (Download, Delete, Restore)
- Create Backup button
- Cleanup Old Backups button

### TypeScript Types

```typescript
interface BackupSettings {
  enabled: boolean;
  interval_hours: number;
  retention_days: number;
  backup_location: string;
  include_database: boolean;
  include_logs: boolean;
  remote_backup?: RemoteBackupSettings;
}

interface RemoteBackupSettings {
  provider: 's3' | 'ftp' | 'sftp';
  endpoint?: string;
  access_key?: string;
  secret_key?: string;
  bucket?: string;
  path: string;
}

interface BackupInfo {
  filename: string;
  created_at: string;
  size_bytes: number;
  location: string;
  is_remote: boolean;
}
```

## Database Migration

**New Column:**
```sql
ALTER TABLE settings ADD COLUMN backup JSON;
```

Note: Migration will be handled by Alembic automatically on next startup.

## Testing

### Manual Testing Steps

1. **Test Backup Creation:**
```bash
curl -X POST http://localhost:8000/api/system/backups/create \
  -H "Authorization: Bearer YOUR_TOKEN"
```

2. **List Backups:**
```bash
curl http://localhost:8000/api/system/backups \
  -H "Authorization: Bearer YOUR_TOKEN"
```

3. **Download Backup:**
```bash
curl -O http://localhost:8000/api/system/backups/marzneshin_backup_20250109_120000.tar.gz/download \
  -H "Authorization: Bearer YOUR_TOKEN"
```

4. **Check Backup Settings:**
```bash
curl http://localhost:8000/api/system/settings/backup \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Automated Tests (TODO)

- Unit tests for BackupManager
- Integration tests for API endpoints
- Test backup/restore cycle
- Test cleanup functionality

## Security Considerations

1. **Access Control:** All backup endpoints require sudo admin authentication
2. **File Path Validation:** Backup filenames are validated to prevent directory traversal
3. **Secure Storage:** Remote backup credentials should be stored securely
4. **Backup Encryption:** Consider encrypting backups (future enhancement)

## Dependencies

**Python Packages:**
- No new required dependencies for basic functionality
- Optional: `boto3` for S3 uploads (install with: `pip install boto3`)

## Future Enhancements

- [ ] Backup encryption
- [ ] Incremental backups
- [ ] Backup verification/integrity checks
- [ ] Email notifications on backup completion/failure
- [ ] Backup to multiple remote locations
- [ ] Compressed backup size optimization
- [ ] Backup scheduling with cron expressions
- [ ] Point-in-time recovery

## Troubleshooting

**Backup Failed:**
- Check logs: `/var/log/marzneshin/`
- Verify disk space: `df -h /var/lib/marzneshin/backups`
- Check database permissions

**PostgreSQL/MySQL Backup Fails:**
- Ensure `pg_dump` or `mysqldump` is installed
- Verify database connection credentials
- Check firewall rules

**Remote Upload Fails:**
- Verify S3/FTP credentials
- Check network connectivity
- Ensure boto3 is installed for S3

## Contributing

To extend this feature:
1. Add new backup providers in `app/utils/backup.py`
2. Update `RemoteBackupSettings` model for new providers
3. Implement upload method (e.g., `_upload_to_provider()`)
4. Add tests
5. Update documentation

## License

AGPL-3.0
