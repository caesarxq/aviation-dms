import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "full_stack_backup_prod.py"
SPEC = importlib.util.spec_from_file_location("full_stack_backup_prod", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)


@pytest.fixture
def backup_module():
    if SPEC is None or SPEC.loader is None:
        pytest.fail("production backup helper is not implemented")
    sys.modules[SPEC.name] = MODULE
    SPEC.loader.exec_module(MODULE)
    return MODULE


def test_backup_config_fails_closed_without_encrypted_remote_prerequisites(backup_module):
    with pytest.raises(backup_module.BackupConfigurationError):
        backup_module.load_config({})


def test_backup_config_requires_verified_encrypted_staging(backup_module):
    config = backup_module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": "/opt/kfl-aviation-dms-prod/backup-tool/app",
            "DMS_BACKUP_STAGING_ROOT": "/var/lib/kfl-dms-backups",
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@10.20.173.120:/srv/backups/kfl-prod",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": "/etc/kfl-dms/secrets/restic-password",
            "DMS_BACKUP_SSH_HOST": "10.20.173.120",
            "DMS_BACKUP_SSH_IDENTITY_FILE": "/etc/kfl-dms/secrets/backup-key",
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": "/etc/kfl-dms/secrets/known_hosts",
        }
    )

    with pytest.raises(backup_module.BackupConfigurationError, match="staging encryption"):
        backup_module.validate_runtime_prerequisites(config, command_exists=lambda _: True)


def test_restic_ssh_command_requires_pinned_host_key(backup_module):
    config = backup_module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": "/opt/kfl-aviation-dms-prod/backup-tool/app",
            "DMS_BACKUP_STAGING_ROOT": "/var/lib/kfl-dms-backups",
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@10.20.173.120:/srv/backups/kfl-prod",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": "/etc/kfl-dms/secrets/restic-password",
            "DMS_BACKUP_SSH_HOST": "10.20.173.120",
            "DMS_BACKUP_SSH_IDENTITY_FILE": "/etc/kfl-dms/secrets/backup-key",
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": "/etc/kfl-dms/secrets/known_hosts",
        }
    )

    restic_env = backup_module.restic_environment(
        config, base_env={"PATH": "/usr/bin", "SMTP_PASS": "not-forwarded"}
    )

    assert "StrictHostKeyChecking=yes" in restic_env["RESTIC_SFTP_COMMAND"]
    assert "UserKnownHostsFile=/etc/kfl-dms/secrets/known_hosts" in restic_env["RESTIC_SFTP_COMMAND"]
    assert "SMTP_PASS" not in restic_env


def test_candidate_worker_is_offline_and_mounts_production_data_read_only(backup_module):
    config = backup_module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": "/opt/kfl-aviation-dms-prod/backup-tool/app",
            "DMS_BACKUP_STAGING_ROOT": "/var/lib/kfl-dms-backups",
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@10.20.173.120:/srv/backups/kfl-prod",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": "/etc/kfl-dms/secrets/restic-password",
            "DMS_BACKUP_SSH_HOST": "10.20.173.120",
            "DMS_BACKUP_SSH_IDENTITY_FILE": "/etc/kfl-dms/secrets/backup-key",
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": "/etc/kfl-dms/secrets/known_hosts",
        }
    )

    command = backup_module.build_candidate_worker_command(
        config,
        "sha256:backend-image",
        Path("/var/lib/kfl-dms-backups/run-1"),
    )

    command_text = " ".join(command)
    ast.parse(command[-1])
    assert "--network none" in command_text
    assert "--read-only" in command_text
    assert "10001:10001" in command_text
    assert "type=volume,src=kfl-aviation-dms-prod_dms_data,dst=/source,readonly" in command_text
    assert "type=bind,src=/opt/kfl-aviation-dms-prod/backup-tool/app,dst=/backup-tool/app,readonly" in command_text


def test_restic_backup_verifies_snapshot_without_pruning(backup_module, tmp_path):
    config = backup_module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": "/opt/kfl-aviation-dms-prod/backup-tool/app",
            "DMS_BACKUP_STAGING_ROOT": "/var/lib/kfl-dms-backups",
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@10.20.173.120:/srv/backups/kfl-prod",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": "/etc/kfl-dms/secrets/restic-password",
            "DMS_BACKUP_SSH_HOST": "10.20.173.120",
            "DMS_BACKUP_SSH_IDENTITY_FILE": "/etc/kfl-dms/secrets/backup-key",
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": "/etc/kfl-dms/secrets/known_hosts",
        }
    )
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        if "snapshots" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps([{"id": "snapshot-123", "tags": ["dms-run-test"]}]),
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    snapshot_id = backup_module.run_restic_backup(
        config,
        candidate,
        source_host="roc-app",
        run_tag="dms-run-test",
        runner=fake_runner,
    )

    assert snapshot_id == "snapshot-123"
    commands = [" ".join(command) for command in calls]
    assert any(" backup " in f" {command} " for command in commands)
    assert any(" snapshots " in f" {command} " for command in commands)
    assert not any(" forget " in f" {command} " or " prune " in f" {command} " for command in commands)


def test_runtime_prerequisites_reject_world_readable_repo_password_file(backup_module, tmp_path):
    app_source = tmp_path / "app"
    app_source.mkdir()
    (app_source / "__init__.py").write_text("")
    (app_source / "backup_create.py").write_text("# test module")
    (app_source / "backup_validation.py").write_text("# test module")
    (app_source / "database.py").write_text("# test module")
    (app_source / "upload_reconciliation.py").write_text("# test module")
    staging = tmp_path / "staging"
    staging.mkdir()
    password_file = tmp_path / "restic-password"
    password_file.write_text("test-only-placeholder")
    password_file.chmod(0o644)
    identity_file = tmp_path / "backup-key"
    identity_file.write_text("test-only-placeholder")
    identity_file.chmod(0o600)
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("test-only-known-host-entry")
    known_hosts.chmod(0o600)
    config = backup_module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": str(app_source),
            "DMS_BACKUP_STAGING_ROOT": str(staging),
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@backup.example:/srv/dms",
            "DMS_BACKUP_STAGING_ENCRYPTED": "true",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": str(password_file),
            "DMS_BACKUP_SSH_HOST": "backup.example",
            "DMS_BACKUP_SSH_IDENTITY_FILE": str(identity_file),
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": str(known_hosts),
        }
    )

    with pytest.raises(backup_module.BackupConfigurationError, match="permissions"):
        backup_module.validate_runtime_prerequisites(
            config,
            command_exists=lambda _: True,
            runner=lambda *args, **kwargs: type("Result", (), {"returncode": 0})(),
        )


def test_runtime_prerequisites_accept_secure_files_with_pinned_host_key(backup_module, tmp_path):
    app_source = tmp_path / "app"
    app_source.mkdir()
    for name in ("__init__.py", "backup_create.py", "backup_validation.py", "database.py", "upload_reconciliation.py"):
        (app_source / name).write_text("# test module")
    staging = tmp_path / "staging"
    staging.mkdir(mode=0o700)
    password_file = tmp_path / "restic-password"
    password_file.write_text("test-only-placeholder")
    password_file.chmod(0o600)
    identity_file = tmp_path / "backup-key"
    identity_file.write_text("test-only-placeholder")
    identity_file.chmod(0o600)
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("test-only-known-host-entry")
    known_hosts.chmod(0o600)
    config = backup_module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": str(app_source),
            "DMS_BACKUP_STAGING_ROOT": str(staging),
            "DMS_BACKUP_STAGING_ENCRYPTED": "true",
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@backup.example:/srv/dms",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": str(password_file),
            "DMS_BACKUP_SSH_HOST": "backup.example",
            "DMS_BACKUP_SSH_IDENTITY_FILE": str(identity_file),
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": str(known_hosts),
        }
    )
    commands = []

    backup_module.validate_runtime_prerequisites(
        config,
        command_exists=lambda _: True,
        runner=lambda command, **kwargs: commands.append(command) or type("Result", (), {"returncode": 0})(),
    )

    assert commands == [["ssh-keygen", "-F", "backup.example", "-f", str(known_hosts)]]


def test_discover_production_source_requires_expected_volume_and_backend(tmp_path, backup_module):
    source = tmp_path / "docker-volume-data"
    source.mkdir()
    config = backup_module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": "/opt/kfl-aviation-dms-prod/backup-tool/app",
            "DMS_BACKUP_STAGING_ROOT": "/var/lib/kfl-dms-backups",
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@10.20.173.120:/srv/backups/kfl-prod",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": "/etc/kfl-dms/secrets/restic-password",
            "DMS_BACKUP_SSH_HOST": "10.20.173.120",
            "DMS_BACKUP_SSH_IDENTITY_FILE": "/etc/kfl-dms/secrets/backup-key",
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": "/etc/kfl-dms/secrets/known_hosts",
        }
    )
    responses = [
        f"{config.volume_name}|{source}\n",
        f"{source}\n",
        "sha256:backend-image\n",
    ]

    result = backup_module.discover_production_source(
        config,
        runner=lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=responses.pop(0),
            stderr="",
        ),
    )

    assert result == (source, "sha256:backend-image")


def test_backup_lock_rejects_overlapping_runs(tmp_path, backup_module):
    with backup_module.backup_lock(tmp_path):
        with pytest.raises(backup_module.BackupConfigurationError, match="already running"):
            with backup_module.backup_lock(tmp_path):
                pass


def test_backup_environment_parser_accepts_only_literal_backup_settings(tmp_path, backup_module):
    config_file = tmp_path / "backup.env"
    config_file.write_text(
        "DMS_BACKUP_VOLUME_NAME=kfl-aviation-dms-prod_dms_data\n"
        "DMS_BACKUP_STAGING_ENCRYPTED=true\n"
    )

    parsed = backup_module.read_backup_environment(config_file, inherited={})

    assert parsed["DMS_BACKUP_VOLUME_NAME"] == "kfl-aviation-dms-prod_dms_data"
    assert parsed["DMS_BACKUP_STAGING_ENCRYPTED"] == "true"

    config_file.write_text("SMTP_PASS=not-a-real-secret\n")
    with pytest.raises(backup_module.BackupConfigurationError, match="unsupported"):
        backup_module.read_backup_environment(config_file, inherited={})
