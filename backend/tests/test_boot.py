"""The startup sequence (docs/PLAN.md §11.4)."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dinnerbell import boot
from dinnerbell.core.clock import FakeClock
from dinnerbell.db import backup, instance_lock, migrate
from tests.support import make_settings

CLOCK = FakeClock(datetime(2026, 10, 6, 14, 0, tzinfo=UTC))


@pytest.fixture(autouse=True)
def _release_locks(tmp_path: Path):
    yield
    for path in list(instance_lock._held):  # pyright: ignore[reportPrivateUsage]
        instance_lock.release(path)


def _epoch(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute("SELECT auth_epoch FROM app_meta").fetchone()[0])
    finally:
        conn.close()


def test_fresh_install_migrates_and_records_the_boot(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data")
    boot.prepare(settings, CLOCK)
    assert migrate.current_revision(settings.db_path) == migrate.head_revision()
    conn = sqlite3.connect(settings.db_path)
    try:
        fp, check, version = conn.execute(
            "SELECT password_fp, secret_key_check, last_boot_version FROM app_meta"
        ).fetchone()
    finally:
        conn.close()
    assert fp and check and version
    assert not (settings.backup_dir / backup.PRE_MIGRATE_DIR).exists()  # nothing to back up yet


def test_changing_the_password_signs_everyone_out(data_dir: Path) -> None:
    boot.prepare(make_settings(data_dir), CLOCK)
    before = _epoch(data_dir / "dinnerbell.db")
    instance_lock.release(data_dir / ".lock")
    boot.prepare(make_settings(data_dir, app_password="a-brand-new-passphrase"), CLOCK)
    assert _epoch(data_dir / "dinnerbell.db") == before + 1


def test_changing_the_secret_key_signs_everyone_out(data_dir: Path) -> None:
    boot.prepare(make_settings(data_dir), CLOCK)
    before = _epoch(data_dir / "dinnerbell.db")
    instance_lock.release(data_dir / ".lock")
    boot.prepare(make_settings(data_dir, app_secret_key="another-secret-" + "1" * 32), CLOCK)
    assert _epoch(data_dir / "dinnerbell.db") == before + 1


def test_a_version_change_takes_a_pre_migration_backup_once(data_dir: Path) -> None:
    settings = make_settings(data_dir)
    boot.prepare(settings, CLOCK)  # the template DB has no last_boot_version yet
    folder = settings.backup_dir / backup.PRE_MIGRATE_DIR
    copies = list(folder.glob("*.db"))
    assert len(copies) == 1
    instance_lock.release(data_dir / ".lock")
    boot.prepare(settings, CLOCK)  # same version, nothing pending: no new copy
    assert list(folder.glob("*.db")) == copies


def test_unknown_revision_exits_65(data_dir: Path) -> None:
    conn = sqlite3.connect(data_dir / "dinnerbell.db")
    conn.execute("UPDATE alembic_version SET version_num = '209912312359'")
    conn.commit()
    conn.close()
    with pytest.raises(boot.BootError) as caught:
        boot.prepare(make_settings(data_dir), CLOCK)
    assert caught.value.exit_code == boot.EXIT_UNKNOWN_REVISION


def test_failed_migration_exits_70_and_keeps_the_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings(tmp_path / "data")
    settings.data_dir.mkdir(parents=True)
    sqlite3.connect(settings.db_path).close()
    before = settings.db_path.read_bytes()

    def broken(db_path: Path) -> str:
        raise migrate.MigrationError("simulated")

    monkeypatch.setattr(migrate, "upgrade", broken)
    with pytest.raises(boot.BootError) as caught:
        boot.prepare(settings, CLOCK)
    assert caught.value.exit_code == boot.EXIT_MIGRATION
    assert settings.db_path.read_bytes() == before


def test_container_requires_a_mounted_volume(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, dinnerbell_container=True)
    with pytest.raises(boot.BootError) as caught:
        boot.check_data_dir(settings, mounts=[boot.MountEntry("/", "overlay")])
    assert caught.value.exit_code == boot.EXIT_DATA_DIR
    assert "not a mounted volume" in caught.value.message


def test_network_filesystems_are_refused(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, dinnerbell_container=True)
    mounts = [boot.MountEntry(str(tmp_path), "nfs4")]
    with pytest.raises(boot.BootError) as caught:
        boot.check_data_dir(settings, mounts=mounts)
    assert "nfs4" in caught.value.message
    allowed = make_settings(tmp_path, dinnerbell_container=True, data_dir_unsafe_fs_ok=True)
    boot.check_data_dir(allowed, mounts=mounts)


def test_unwritable_data_dir_explains_the_fix(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    data.chmod(0o500)
    try:
        with pytest.raises(boot.BootError) as caught:
            boot.check_data_dir(make_settings(data))
    finally:
        data.chmod(0o700)
    assert caught.value.exit_code == boot.EXIT_DATA_DIR
    assert "chown" in caught.value.message


def test_mountinfo_parsing(tmp_path: Path) -> None:
    sample = tmp_path / "mountinfo"
    sample.write_text(
        "36 35 98:0 /mnt1 /data rw,noatime master:1 - ext4 /dev/root rw\n"
        "37 35 0:42 / /my\\040files rw - nfs4 server:/x rw\n"
    )
    entries = boot.read_mounts(sample)
    assert entries == [boot.MountEntry("/data", "ext4"), boot.MountEntry("/my files", "nfs4")]


def test_a_second_process_cannot_take_the_lock(tmp_path: Path) -> None:
    lock = tmp_path / ".lock"
    instance_lock.acquire(lock)
    script = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        from dinnerbell.db import instance_lock
        try:
            instance_lock.acquire(Path({str(lock)!r}))
        except instance_lock.InstanceLockError:
            sys.exit(3)
        sys.exit(0)
        """
    )
    result = subprocess.run([sys.executable, "-c", script], check=False)  # noqa: S603
    assert result.returncode == 3
