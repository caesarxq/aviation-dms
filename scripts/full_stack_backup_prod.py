"""Fail-closed production DMS backup orchestration."""

from __future__ import annotations

import json
import os
import fcntl
import re
import shutil
import socket
import stat
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from shlex import join as shell_join
import subprocess
from contextlib import contextmanager
from typing import Mapping

PRODUCTION_VOLUME = "kfl-aviation-dms-prod_dms_data"
PRODUCTION_BACKEND_CONTAINER = "kfl-aviation-dms-prod-backend-1"
_CANDIDATE_RE = re.compile(r"^dms-backup-\d{8}T\d{6}Z$")
_BACKUP_ENV_KEYS = frozenset(
    {
        "DMS_BACKUP_VOLUME_NAME",
        "DMS_BACKUP_BACKEND_CONTAINER",
        "DMS_BACKUP_APP_SOURCE",
        "DMS_BACKUP_STAGING_ROOT",
        "DMS_BACKUP_STAGING_ENCRYPTED",
        "DMS_BACKUP_RESTIC_REPOSITORY",
        "DMS_BACKUP_RESTIC_PASSWORD_FILE",
        "DMS_BACKUP_SSH_HOST",
        "DMS_BACKUP_SSH_IDENTITY_FILE",
        "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE",
    }
)


class BackupConfigurationError(RuntimeError):
    """Raised when a required production backup prerequisite is absent."""


def read_backup_environment(
    path: Path, inherited: Mapping[str, str]
) -> dict[str, str]:
    """Read only allow-listed literal backup settings; never source shell code."""
    environment = dict(inherited)
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return environment
    except OSError as exc:
        raise BackupConfigurationError("Backup configuration file is inaccessible") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise BackupConfigurationError("Backup configuration must be a regular file")
    if stat.S_IMODE(info.st_mode) & 0o022:
        raise BackupConfigurationError("Backup configuration must not be group/world writable")
    if hasattr(os, "geteuid") and os.geteuid() == 0 and info.st_uid != 0:
        raise BackupConfigurationError("Backup configuration must be root-owned")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise BackupConfigurationError("Backup configuration could not be read safely") from exc
    for line in lines:
        value_line = line.strip()
        if not value_line or value_line.startswith("#"):
            continue
        if "=" not in value_line:
            raise BackupConfigurationError("Backup configuration contains an invalid line")
        key, value = value_line.split("=", 1)
        key = key.strip()
        if key not in _BACKUP_ENV_KEYS or "\x00" in value:
            raise BackupConfigurationError("Backup configuration contains an unsupported setting")
        environment.setdefault(key, value.strip())
    return environment


@dataclass(frozen=True)
class BackupConfig:
    volume_name: str
    backend_container: str
    staging_encrypted: bool
    app_source: Path
    staging_root: Path
    restic_repository: str
    restic_password_file: Path
    ssh_host: str
    ssh_identity_file: Path
    ssh_known_hosts_file: Path


def load_config(env: Mapping[str, str]) -> BackupConfig:
    """Load non-secret settings and paths; never read credential file contents."""
    required = (
        "DMS_BACKUP_APP_SOURCE",
        "DMS_BACKUP_STAGING_ROOT",
        "DMS_BACKUP_RESTIC_REPOSITORY",
        "DMS_BACKUP_RESTIC_PASSWORD_FILE",
        "DMS_BACKUP_SSH_HOST",
        "DMS_BACKUP_SSH_IDENTITY_FILE",
        "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE",
    )
    missing = [name for name in required if not env.get(name, "").strip()]
    if missing:
        raise BackupConfigurationError(
            "Required production backup settings are missing: " + ", ".join(missing)
        )

    volume_name = env.get("DMS_BACKUP_VOLUME_NAME", PRODUCTION_VOLUME).strip()
    backend_container = env.get(
        "DMS_BACKUP_BACKEND_CONTAINER", PRODUCTION_BACKEND_CONTAINER
    ).strip()
    if volume_name != PRODUCTION_VOLUME:
        raise BackupConfigurationError("Refusing a non-production DMS volume")
    if backend_container != PRODUCTION_BACKEND_CONTAINER:
        raise BackupConfigurationError("Refusing a non-production backend container")

    restic_repository = env["DMS_BACKUP_RESTIC_REPOSITORY"].strip()
    ssh_host = env["DMS_BACKUP_SSH_HOST"].strip()
    if not restic_repository.startswith("sftp:") or f"@{ssh_host}:" not in restic_repository:
        raise BackupConfigurationError(
            "RESTIC repository must use the configured pinned SFTP backup host"
        )

    paths = {
        name: Path(env[name].strip())
        for name in (
            "DMS_BACKUP_APP_SOURCE",
            "DMS_BACKUP_STAGING_ROOT",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE",
            "DMS_BACKUP_SSH_IDENTITY_FILE",
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE",
        )
    }
    if any(not path.is_absolute() for path in paths.values()):
        raise BackupConfigurationError("Backup paths must be absolute")

    return BackupConfig(
        volume_name=volume_name,
        backend_container=backend_container,
        staging_encrypted=env.get("DMS_BACKUP_STAGING_ENCRYPTED", "").strip().lower() == "true",
        app_source=paths["DMS_BACKUP_APP_SOURCE"],
        staging_root=paths["DMS_BACKUP_STAGING_ROOT"],
        restic_repository=restic_repository,
        restic_password_file=paths["DMS_BACKUP_RESTIC_PASSWORD_FILE"],
        ssh_host=ssh_host,
        ssh_identity_file=paths["DMS_BACKUP_SSH_IDENTITY_FILE"],
        ssh_known_hosts_file=paths["DMS_BACKUP_SSH_KNOWN_HOSTS_FILE"],
    )


def restic_environment(
    config: BackupConfig, base_env: Mapping[str, str]
) -> dict[str, str]:
    """Build a Restic environment with a pinned SSH host key and file credentials."""
    environment = {
        name: base_env[name]
        for name in ("PATH", "HOME", "LANG", "LC_ALL")
        if name in base_env
    }
    ssh_command = shell_join(
        (
            "ssh",
            "-i",
            str(config.ssh_identity_file),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            f"UserKnownHostsFile={config.ssh_known_hosts_file}",
            "-o",
            "StrictHostKeyChecking=yes",
            "-s",
            "sftp",
        )
    )
    environment.update(
        {
            "RESTIC_REPOSITORY": config.restic_repository,
            "RESTIC_PASSWORD_FILE": str(config.restic_password_file),
            "RESTIC_CACHE_DIR": str(config.staging_root / "restic-cache"),
            "RESTIC_SFTP_COMMAND": ssh_command,
        }
    )
    return environment


def build_candidate_worker_command(
    config: BackupConfig,
    image_id: str,
    candidate_root: Path,
) -> list[str]:
    """Build a network-isolated worker command with read-only DMS source mounts."""
    if not candidate_root.is_absolute() or not image_id:
        raise BackupConfigurationError("Candidate path and backend image are required")
    candidate_root = candidate_root.resolve()
    worker_code = (
        "import asyncio; from pathlib import Path; "
        "from app.backup_create import create_backup_candidate; "
        "result = asyncio.run(create_backup_candidate('/source', '/candidate')); "
        "assert result.get('accepted', False); "
        "print(Path(result['candidate_path']).name)"
    )
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "10001:10001",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "64",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--mount",
        f"type=volume,src={config.volume_name},dst=/source,readonly",
        "--mount",
        f"type=bind,src={candidate_root},dst=/candidate",
        "--mount",
        f"type=bind,src={config.app_source},dst=/backup-tool/app,readonly",
        "--env",
        "PYTHONPATH=/backup-tool",
        "--env",
        "DMS_DB_PATH=/source/dms.db",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--entrypoint",
        "python",
        image_id,
        "-c",
        worker_code,
    ]


def run_restic_backup(
    config: BackupConfig,
    candidate: Path,
    *,
    source_host: str,
    run_tag: str,
    runner=subprocess.run,
) -> str:
    """Upload an encrypted snapshot and confirm its Restic snapshot id.

    Retention/pruning is intentionally not performed until the Records
    Custodian approves a retention policy.
    """
    candidate = Path(candidate)
    if not candidate.is_absolute() or not candidate.is_dir() or candidate.is_symlink():
        raise BackupConfigurationError("Backup candidate must be an isolated regular directory")
    if not source_host or not run_tag:
        raise BackupConfigurationError("Backup host and run tag are required")

    environment = restic_environment(
        config,
        {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/root"),
        },
    )
    base_command = [
        "restic",
        "--repo",
        config.restic_repository,
        "--password-file",
        str(config.restic_password_file),
    ]
    backup_result = runner(
        base_command
        + [
            "backup",
            "--host",
            source_host,
            "--tag",
            "aviation-dms",
            "--tag",
            "production",
            "--tag",
            run_tag,
            "--quiet",
            str(candidate),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if backup_result.returncode != 0:
        raise BackupConfigurationError("Encrypted Restic backup command failed")

    verify_result = runner(
        base_command + ["snapshots", "--json", "--host", source_host, "--tag", run_tag],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if verify_result.returncode != 0:
        raise BackupConfigurationError("Restic snapshot verification command failed")
    try:
        snapshots = json.loads(verify_result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BackupConfigurationError("Restic returned invalid snapshot metadata") from exc
    matching = [
        item for item in snapshots
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and run_tag in (item.get("tags") or [])
    ]
    if not matching:
        raise BackupConfigurationError("Restic did not confirm the new backup snapshot")
    return matching[-1]["id"]


def validate_runtime_prerequisites(
    config: BackupConfig,
    *,
    command_exists=shutil.which,
    runner=subprocess.run,
) -> None:
    """Fail closed unless dependencies, secret-file modes, and host pin exist."""
    if not config.staging_encrypted:
        raise BackupConfigurationError(
            "Backup staging encryption must be verified and explicitly set to true"
        )
    for command in ("docker", "restic", "ssh", "ssh-keygen"):
        if not command_exists(command):
            raise BackupConfigurationError(f"Required backup command is missing: {command}")

    if config.app_source.is_symlink() or not config.app_source.is_dir():
        raise BackupConfigurationError("Backup application source directory is unavailable")
    for filename in (
        "__init__.py",
        "backup_create.py",
        "backup_validation.py",
        "database.py",
        "upload_reconciliation.py",
    ):
        if not (config.app_source / filename).is_file():
            raise BackupConfigurationError("Backup application source is incomplete")

    def require_private_regular_file(path: Path, label: str) -> None:
        try:
            info = path.lstat()
        except OSError as exc:
            raise BackupConfigurationError(f"Required {label} file is unavailable") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise BackupConfigurationError(f"Required {label} must be a regular file")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise BackupConfigurationError(f"Required {label} file permissions must be 0600 or stricter")
        if hasattr(os, "geteuid") and os.geteuid() == 0 and info.st_uid != 0:
            raise BackupConfigurationError(f"Required {label} file must be root-owned")

    require_private_regular_file(config.restic_password_file, "Restic password")
    require_private_regular_file(config.ssh_identity_file, "backup SSH identity")

    try:
        host_info = config.ssh_known_hosts_file.lstat()
    except OSError as exc:
        raise BackupConfigurationError("Pinned SSH known_hosts file is unavailable") from exc
    if stat.S_ISLNK(host_info.st_mode) or not stat.S_ISREG(host_info.st_mode):
        raise BackupConfigurationError("Pinned SSH known_hosts must be a regular file")
    if stat.S_IMODE(host_info.st_mode) & 0o022:
        raise BackupConfigurationError("Pinned SSH known_hosts must not be group/world writable")
    if hasattr(os, "geteuid") and os.geteuid() == 0 and host_info.st_uid != 0:
        raise BackupConfigurationError("Pinned SSH known_hosts must be root-owned")

    pin_result = runner(
        ["ssh-keygen", "-F", config.ssh_host, "-f", str(config.ssh_known_hosts_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    if pin_result.returncode != 0:
        raise BackupConfigurationError("Backup host key is not pinned in known_hosts")


def discover_production_source(config: BackupConfig, runner=subprocess.run) -> tuple[Path, str]:
    """Verify the named production volume is mounted at /app/data and get image id."""
    template = '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}|{{.Source}}{{end}}{{end}}'
    mount_result = runner(
        ["docker", "inspect", "--format", template, config.backend_container],
        capture_output=True,
        text=True,
        check=False,
    )
    if mount_result.returncode != 0:
        raise BackupConfigurationError("Could not inspect production backend volume")
    mount_line = mount_result.stdout.strip()
    if "|" not in mount_line:
        raise BackupConfigurationError("Production backend has no /app/data volume mount")
    volume_name, source_path = mount_line.split("|", 1)
    source_root = Path(source_path)
    if (
        volume_name != config.volume_name
        or not source_root.is_absolute()
        or source_root.is_symlink()
        or not source_root.is_dir()
    ):
        raise BackupConfigurationError("Production backend data volume does not match configured volume")

    volume_result = runner(
        ["docker", "volume", "inspect", "--format", "{{.Mountpoint}}", config.volume_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if volume_result.returncode != 0 or Path(volume_result.stdout.strip()).resolve() != source_root.resolve():
        raise BackupConfigurationError("Production Docker volume mountpoint could not be verified")

    image_result = runner(
        ["docker", "inspect", "--format", "{{.Image}}", config.backend_container],
        capture_output=True,
        text=True,
        check=False,
    )
    image_id = image_result.stdout.strip()
    if image_result.returncode != 0 or not image_id:
        raise BackupConfigurationError("Could not identify the running production backend image")
    return source_root, image_id


def _prepare_staging_root(path: Path) -> None:
    if path.is_symlink():
        raise BackupConfigurationError("Backup staging root must not be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise BackupConfigurationError("Backup staging root is not a directory")
    os.chmod(path, 0o700)


@contextmanager
def backup_lock(staging_root: Path):
    """Prevent overlapping scheduled and pre-deployment backup runs."""
    staging_root = Path(staging_root)
    if staging_root.is_symlink():
        raise BackupConfigurationError("Backup staging root must not be a symlink")
    if not staging_root.is_dir():
        raise BackupConfigurationError("Backup staging root must exist before locking")
    lock_path = staging_root / ".backup.lock"
    descriptor = os.open(
        lock_path,
        os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    acquired = False
    try:
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError as exc:
            raise BackupConfigurationError("Another production backup is already running") from exc
        yield
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _estimate_data_size(source_root: Path) -> int:
    total = 0
    for current, directories, files in os.walk(source_root, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            path = current_path / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise BackupConfigurationError("DMS data contains a symlink; refusing backup")
            if not stat.S_ISDIR(info.st_mode):
                raise BackupConfigurationError("DMS data contains an unsupported filesystem entry")
        for name in files:
            path = current_path / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise BackupConfigurationError("DMS data contains an unsupported filesystem entry")
            total += info.st_size
    return total


def _run_candidate_worker(
    config: BackupConfig,
    image_id: str,
    candidate_parent: Path,
    *,
    runner=subprocess.run,
) -> Path:
    command = build_candidate_worker_command(config, image_id, candidate_parent)
    result = runner(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise BackupConfigurationError("DMS backup candidate failed integrity validation")
    candidate_names = [
        line.strip()
        for line in result.stdout.splitlines()
        if _CANDIDATE_RE.fullmatch(line.strip())
    ]
    if len(candidate_names) != 1:
        raise BackupConfigurationError("DMS backup worker did not return one candidate identifier")
    candidate = candidate_parent / candidate_names[0]
    if candidate.is_symlink() or not candidate.is_dir() or candidate.parent.resolve() != candidate_parent.resolve():
        raise BackupConfigurationError("DMS backup candidate path is unsafe")
    return candidate


def _run_backup_unlocked(
    config: BackupConfig,
    source_root: Path,
    image_id: str,
    *,
    runner=subprocess.run,
) -> str:
    """Create, validate, encrypt, and confirm a production DMS snapshot."""
    required_free = _estimate_data_size(source_root)
    if shutil.disk_usage(config.staging_root).free < required_free:
        raise BackupConfigurationError("Insufficient free space for isolated backup candidate")

    job_root = Path(tempfile.mkdtemp(prefix="kfl-dms-prod-", dir=config.staging_root))
    os.chmod(job_root, 0o750)
    if hasattr(os, "chown"):
        os.chown(job_root, 0, 10001)
    try:
        candidate_parent = job_root / "candidate"
        candidate_parent.mkdir(mode=0o700)
        if hasattr(os, "chown"):
            os.chown(candidate_parent, 10001, 10001)
        candidate = _run_candidate_worker(config, image_id, candidate_parent, runner=runner)
        run_tag = f"dms-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        return run_restic_backup(
            config,
            candidate,
            source_host=socket.gethostname(),
            run_tag=run_tag,
            runner=runner,
        )
    finally:
        shutil.rmtree(job_root, ignore_errors=True)


def run_backup(config: BackupConfig, *, runner=subprocess.run) -> str:
    validate_runtime_prerequisites(config, runner=runner)
    source_root, image_id = discover_production_source(config, runner=runner)
    if config.staging_root.is_symlink():
        raise BackupConfigurationError("Backup staging root must not be a symlink")
    source_resolved = source_root.resolve()
    staging_resolved = config.staging_root.resolve(strict=False)
    if (
        source_resolved == staging_resolved
        or source_resolved.is_relative_to(staging_resolved)
        or staging_resolved.is_relative_to(source_resolved)
    ):
        raise BackupConfigurationError("Backup staging root overlaps the live DMS volume")
    _prepare_staging_root(config.staging_root)
    with backup_lock(config.staging_root):
        return _run_backup_unlocked(config, source_root, image_id, runner=runner)


def main() -> int:
    try:
        environment = read_backup_environment(
            Path("/etc/kfl-aviation-dms-prod/backup.env"), os.environ
        )
        config = load_config(environment)
        snapshot_id = run_backup(config)
    except BackupConfigurationError as exc:
        print(f"ERROR: production DMS backup failed closed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: production DMS backup aborted ({type(exc).__name__})", file=sys.stderr)
        return 3
    print(f"PASS: encrypted production DMS snapshot confirmed: {snapshot_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
