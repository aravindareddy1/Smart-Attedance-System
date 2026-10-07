import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from flask import current_app
from app.utils import log_audit


def get_backups_dir() -> Path:
    backup_dir = Path(current_app.config['BACKUPS_DIR'])
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_database_backup(user_id: Optional[int] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Safely creates a consistent timestamped backup of SQLite database.
    """
    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    if not db_uri.startswith('sqlite:///'):
        return False, "Automated hot-backup is currently configured for SQLite databases.", None

    db_path = db_uri.replace('sqlite:///', '')
    db_file = Path(db_path)
    if not db_file.is_absolute():
        db_file = Path(current_app.root_path).parent / db_path

    if not db_file.exists():
        return False, f"Source database file not found at {db_file}.", None

    backup_dir = get_backups_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"smart_attendance_backup_{timestamp}.db"
    dest_path = backup_dir / backup_filename

    try:
        # Use sqlite3 backup API for transactional consistency
        src_conn = sqlite3.connect(str(db_file))
        dst_conn = sqlite3.connect(str(dest_path))
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        dst_conn.close()
        src_conn.close()

        log_audit('DATABASE_BACKUP', 'System', None, {
            'backup_file': backup_filename,
            'size_bytes': dest_path.stat().st_size
        }, user_id=user_id)

        return True, f"Backup successfully created: {backup_filename}", backup_filename
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        return False, f"Database backup failed: {str(e)}", None


def list_backups() -> List[Dict[str, Any]]:
    """Lists existing database backups sorted by newest first."""
    backup_dir = get_backups_dir()
    backups = []
    for f in backup_dir.glob('*.db'):
        stat = f.stat()
        backups.append({
            'filename': f.name,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'size_bytes': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        })
    backups.sort(key=lambda x: x['filename'], reverse=True)
    return backups
