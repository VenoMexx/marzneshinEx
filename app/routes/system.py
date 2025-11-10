from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db import crud
from app.db.models import Admin as DBAdmin, Settings
from app.db.models import Node
from app.dependencies import (
    DBDep,
    AdminDep,
    SudoAdminDep,
    EndDateDep,
    StartDateDep,
)
from app.models.node import NodeStatus
from app.models.settings import (
    SubscriptionSettings,
    TelegramSettings,
    BackupSettings,
    BackupInfo,
    CloudflareSettings,
    CloudflareIPInfo,
    DoHSettings,
)
from app.models.proxy_mode import ProxyModeSettings
from app.models.system import (
    UsersStats,
    NodesStats,
    AdminsStats,
    TrafficUsageSeries,
)
from app.models.user import UserExpireStrategy
from app.utils.backup import BackupManager
from app.utils.cloudflare import (
    CloudflareAPI,
    get_optimal_cdn_ips,
    get_cloudflare_cdn_ips,
)

router = APIRouter(tags=["System"], prefix="/system")


@router.get("/settings/subscription", response_model=SubscriptionSettings)
def get_subscription_settings(db: DBDep, admin: SudoAdminDep):
    return db.query(Settings.subscription).first()[0]


@router.put("/settings/subscription", response_model=SubscriptionSettings)
def update_subscription_settings(
    db: DBDep, modifications: SubscriptionSettings, admin: SudoAdminDep
):
    settings = db.query(Settings).first()
    settings.subscription = modifications.model_dump(mode="json")
    db.commit()
    return settings.subscription


@router.get("/settings/telegram", response_model=TelegramSettings | None)
def get_telegram_settings(db: DBDep, admin: SudoAdminDep):
    return db.query(Settings.telegram).first().telegram


@router.put("/settings/telegram", response_model=TelegramSettings | None)
def update_telegram_settings(
    db: DBDep, new_telegram: TelegramSettings | None, admin: SudoAdminDep
):
    settings = db.query(Settings.telegram).first()
    settings.telegram = new_telegram
    db.commit()
    return settings.telegram


@router.get("/stats/admins", response_model=AdminsStats)
def get_admins_stats(db: DBDep, admin: SudoAdminDep):
    return AdminsStats(total=db.query(DBAdmin).count())


@router.get("/stats/nodes", response_model=NodesStats)
def get_nodes_stats(db: DBDep, admin: SudoAdminDep):
    return NodesStats(
        total=db.query(Node).count(),
        healthy=db.query(Node)
        .filter(Node.status == NodeStatus.healthy)
        .count(),
        unhealthy=db.query(Node)
        .filter(Node.status == NodeStatus.unhealthy)
        .count(),
    )


@router.get("/stats/traffic", response_model=TrafficUsageSeries)
def get_total_traffic_stats(
    db: DBDep, admin: AdminDep, start_date: StartDateDep, end_date: EndDateDep
):
    return crud.get_total_usages(db, admin, start_date, end_date)


@router.get("/stats/users", response_model=UsersStats)
def get_users_stats(db: DBDep, admin: AdminDep):
    return UsersStats(
        total=crud.get_users_count(
            db, admin=admin if not admin.is_sudo else None
        ),
        active=crud.get_users_count(
            db, admin=admin if not admin.is_sudo else None, is_active=True
        ),
        on_hold=crud.get_users_count(
            db,
            admin=admin if not admin.is_sudo else None,
            expire_strategy=UserExpireStrategy.START_ON_FIRST_USE,
        ),
        expired=crud.get_users_count(
            db,
            admin=admin if not admin.is_sudo else None,
            expired=True,
        ),
        limited=crud.get_users_count(
            db,
            admin=admin if not admin.is_sudo else None,
            data_limit_reached=True,
        ),
        online=crud.get_users_count(
            db, admin=admin if not admin.is_sudo else None, online=True
        ),
    )


# Backup Management Endpoints

@router.get("/settings/backup", response_model=BackupSettings)
def get_backup_settings(db: DBDep, admin: SudoAdminDep):
    """Get current backup settings"""
    settings_row = db.query(Settings.backup).first()
    if not settings_row or not settings_row[0]:
        return BackupSettings()
    return BackupSettings.model_validate(settings_row[0])


@router.put("/settings/backup", response_model=BackupSettings)
def update_backup_settings(
    db: DBDep, modifications: BackupSettings, admin: SudoAdminDep
):
    """Update backup settings"""
    settings = db.query(Settings).first()
    settings.backup = modifications.model_dump(mode="json")
    db.commit()
    return settings.backup


@router.get("/backups", response_model=list[BackupInfo])
async def list_backups(db: DBDep, admin: SudoAdminDep):
    """List all available backups"""
    backup_settings = get_backup_settings(db, admin)
    backup_manager = BackupManager(backup_settings)
    return await backup_manager.list_backups()


@router.post("/backups/create", response_model=BackupInfo)
async def create_backup(db: DBDep, admin: SudoAdminDep):
    """Create a new backup manually"""
    backup_settings = get_backup_settings(db, admin)
    backup_manager = BackupManager(backup_settings)
    backup_info = await backup_manager.create_backup()

    if not backup_info:
        raise HTTPException(status_code=500, detail="Backup creation failed")

    return backup_info


@router.get("/backups/{filename}/download")
async def download_backup(filename: str, db: DBDep, admin: SudoAdminDep):
    """Download a specific backup file"""
    backup_settings = get_backup_settings(db, admin)
    backup_manager = BackupManager(backup_settings)

    backups = await backup_manager.list_backups()
    backup = next((b for b in backups if b.filename == filename), None)

    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    return FileResponse(
        path=backup.location,
        filename=filename,
        media_type="application/gzip"
    )


@router.delete("/backups/{filename}")
async def delete_backup(filename: str, db: DBDep, admin: SudoAdminDep):
    """Delete a specific backup"""
    backup_settings = get_backup_settings(db, admin)
    backup_manager = BackupManager(backup_settings)

    success = await backup_manager.delete_backup(filename)

    if not success:
        raise HTTPException(status_code=404, detail="Backup not found or deletion failed")

    return {"message": f"Backup {filename} deleted successfully"}


@router.post("/backups/{filename}/restore")
async def restore_backup(filename: str, db: DBDep, admin: SudoAdminDep):
    """Restore from a specific backup"""
    backup_settings = get_backup_settings(db, admin)
    backup_manager = BackupManager(backup_settings)

    success = await backup_manager.restore_backup(filename)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Backup restore failed. Please check logs for details."
        )

    return {"message": f"Backup {filename} restored successfully"}


@router.post("/backups/cleanup")
async def cleanup_old_backups(db: DBDep, admin: SudoAdminDep):
    """Manually trigger cleanup of old backups"""
    backup_settings = get_backup_settings(db, admin)
    backup_manager = BackupManager(backup_settings)

    await backup_manager.cleanup_old_backups()

    return {"message": "Old backups cleaned up successfully"}


# Cloudflare/CDN Management Endpoints

@router.get("/settings/cloudflare", response_model=CloudflareSettings)
def get_cloudflare_settings(db: DBDep, admin: SudoAdminDep):
    """Get current Cloudflare/CDN settings"""
    settings_row = db.query(Settings.cloudflare).first()
    if not settings_row or not settings_row[0]:
        return CloudflareSettings()
    return CloudflareSettings.model_validate(settings_row[0])


@router.put("/settings/cloudflare", response_model=CloudflareSettings)
def update_cloudflare_settings(
    db: DBDep, modifications: CloudflareSettings, admin: SudoAdminDep
):
    """Update Cloudflare/CDN settings"""
    settings = db.query(Settings).first()
    settings.cloudflare = modifications.model_dump(mode="json")
    db.commit()
    return settings.cloudflare


@router.post("/cloudflare/verify-token")
async def verify_cloudflare_token(db: DBDep, admin: SudoAdminDep):
    """Verify Cloudflare API token"""
    cf_settings = get_cloudflare_settings(db, admin)

    if not cf_settings.api_token:
        raise HTTPException(
            status_code=400, detail="Cloudflare API token not configured"
        )

    cf_api = CloudflareAPI(cf_settings.api_token, cf_settings.email)
    is_valid = await cf_api.verify_token()

    return {"valid": is_valid}


@router.get("/cloudflare/zones")
async def list_cloudflare_zones(db: DBDep, admin: SudoAdminDep):
    """List all Cloudflare zones (domains)"""
    cf_settings = get_cloudflare_settings(db, admin)

    if not cf_settings.api_token:
        raise HTTPException(
            status_code=400, detail="Cloudflare API token not configured"
        )

    cf_api = CloudflareAPI(cf_settings.api_token, cf_settings.email)
    zones = await cf_api.list_zones()

    return {"zones": zones}


@router.get("/cloudflare/zones/{zone_id}/dns-records")
async def list_dns_records(zone_id: str, db: DBDep, admin: SudoAdminDep):
    """List DNS records for a specific zone"""
    cf_settings = get_cloudflare_settings(db, admin)

    if not cf_settings.api_token:
        raise HTTPException(
            status_code=400, detail="Cloudflare API token not configured"
        )

    cf_api = CloudflareAPI(cf_settings.api_token, cf_settings.email)
    records = await cf_api.list_dns_records(zone_id)

    return {"records": records}


@router.post("/cloudflare/zones/{zone_id}/dns-records")
async def create_dns_record(
    zone_id: str,
    record_type: str,
    name: str,
    content: str,
    proxied: bool = True,
    db: DBDep = None,
    admin: SudoAdminDep = None,
):
    """Create a new DNS record"""
    cf_settings = get_cloudflare_settings(db, admin)

    if not cf_settings.api_token:
        raise HTTPException(
            status_code=400, detail="Cloudflare API token not configured"
        )

    cf_api = CloudflareAPI(cf_settings.api_token, cf_settings.email)
    record = await cf_api.create_dns_record(
        zone_id, record_type, name, content, proxied
    )

    if not record:
        raise HTTPException(status_code=500, detail="Failed to create DNS record")

    return {"record": record}


@router.get("/cdn/optimal-ips", response_model=list[CloudflareIPInfo])
async def get_optimal_cdn_ips_endpoint(
    count: int = 10, admin: SudoAdminDep = None
):
    """Get optimal CDN IP addresses based on latency testing"""
    cdn_ips = await get_optimal_cdn_ips(count=count)
    return cdn_ips


@router.get("/cdn/available-ips")
async def get_available_cdn_ips(admin: SudoAdminDep = None):
    """Get list of available Cloudflare CDN IP addresses"""
    cdn_ips = await get_cloudflare_cdn_ips()
    return {"cdn_ips": cdn_ips}


# DNS over HTTPS (DoH) Management Endpoints

@router.get("/settings/doh", response_model=DoHSettings)
def get_doh_settings(db: DBDep, admin: SudoAdminDep):
    """Get current DNS over HTTPS settings"""
    settings_row = db.query(Settings.doh).first()
    if not settings_row or not settings_row[0]:
        return DoHSettings()
    return DoHSettings.model_validate(settings_row[0])


@router.put("/settings/doh", response_model=DoHSettings)
def update_doh_settings(
    db: DBDep, modifications: DoHSettings, admin: SudoAdminDep
):
    """
    Update DNS over HTTPS settings

    Configure DoH servers for enhanced privacy and security.
    When enabled, DNS queries will be encrypted over HTTPS.

    **Features:**
    - Encrypted DNS queries for privacy
    - CDN-optimized DoH when Cloudflare is enabled
    - Custom host mappings for domain resolution
    - Fallback to standard DNS if DoH fails
    """
    settings = db.query(Settings).first()
    settings.doh = modifications.model_dump(mode="json")
    db.commit()
    return settings.doh


@router.post("/doh/test-server")
async def test_doh_server(server_url: str, db: DBDep, admin: SudoAdminDep):
    """
    Test a DNS over HTTPS server

    **Parameters:**
    - `server_url`: DoH server URL (e.g., https://cloudflare-dns.com/dns-query)

    **Returns:** Server response time and status
    """
    import httpx
    import time

    # Test query for google.com (A record)
    dns_query = {
        "name": "google.com",
        "type": "A"
    }

    try:
        start_time = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                server_url,
                params=dns_query,
                headers={"accept": "application/dns-json"}
            )
        response_time = (time.time() - start_time) * 1000  # Convert to ms

        if response.status_code == 200:
            return {
                "status": "success",
                "server": server_url,
                "response_time_ms": round(response_time, 2),
                "data": response.json()
            }
        else:
            return {
                "status": "error",
                "server": server_url,
                "error": f"HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "status": "error",
            "server": server_url,
            "error": str(e)
        }


# Smart Proxy Mode Management Endpoints

@router.get("/settings/proxy-mode", response_model=ProxyModeSettings)
def get_proxy_mode_settings(db: DBDep, admin: SudoAdminDep):
    """Get current Smart Proxy Mode settings"""
    settings_row = db.query(Settings.proxy_mode).first()
    if not settings_row or not settings_row[0]:
        return ProxyModeSettings()
    return ProxyModeSettings.model_validate(settings_row[0])


@router.put("/settings/proxy-mode", response_model=ProxyModeSettings)
def update_proxy_mode_settings(
    db: DBDep, modifications: ProxyModeSettings, admin: SudoAdminDep
):
    """Update Smart Proxy Mode settings"""
    settings = db.query(Settings).first()
    settings.proxy_mode = modifications.model_dump(mode="json")
    db.commit()
    return settings.proxy_mode
