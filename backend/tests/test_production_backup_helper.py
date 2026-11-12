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


def _runtime_config(module, tmp_path, password_mode=0o600):
    app_source = tmp_path / "app"
    app_source.mkdir()
    for name in ("__init__.py", "backup_create.py", "backup_validation.py", "database.py", "upload_reconciliation.py"):
        (app_source / name).write_text("# test module")
    staging = tmp_path / "encrypted-staging"
    staging.mkdir(mode=0o700)
    password_file = tmp_path / "restic-password"
    password_file.write_text("test-only-placeholder")
    password_file.chmod(password_mode)
    identity_file = tmp_path / "backup-key"
    identity_file.write_text("test-only-placeholder")
    identity_file.chmod(0o600)
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("test-only-known-host-entry")
    known_hosts.chmod(0o600)
    attestation_file = tmp_path / "staging-encryption.json"
    attestation_file.write_text(
        json.dumps(
            {
                "provider": "OCI",
                "mountpoint": str(staging),
                "source": "/dev/mapper/kfl-dms-backups",
                "encrypted_at_rest": True,
                "volume_ocid": "ocid1.volume.oc1..test",
                "kms_key_ocid": "ocid1.key.oc1..test",
                "verified_by": "test-operations",
                "verified_at": "2026-11-12T18:00:00Z",
                "verification_reference": "change-test-1",
            }
        )
    )
    attestation_file.chmod(0o600)
    config = module.load_config(
        {
            "DMS_BACKUP_APP_SOURCE": str(app_source),
            "DMS_BACKUP_STAGING_ROOT": str(staging),
            "DMS_BACKUP_STAGING_ATTESTATION_FILE": str(attestation_file),
            "DMS_BACKUP_RESTIC_REPOSITORY": "sftp:backup@backup.example:/srv/dms",
            "DMS_BACKUP_RESTIC_PASSWORD_FILE": str(password_file),
            "DMS_BACKUP_SSH_HOST": "backup.example",
            "DMS_BACKUP_SSH_IDENTITY_FILE": str(identity_file),
            "DMS_BACKUP_SSH_KNOWN_HOSTS_FILE": str(known_hosts),
        }
    )
    return config, staging


def _runtime_runner(
    staging,
    commands,
    *,
    mount_status=0,
    host_pin_status=0,
    mount_source="/dev/mapper/kfl-dms-backups",
    mount_major_minor="253:1",
    root_source="/dev/root",
    root_major_minor="8:1",
):
    def run(command, **kwargs):
        commands.append(command)
        if command[0] == "findmnt" and "--mountpoint" in command:
            return SimpleNamespace(
                returncode=mount_status,
                stdout=f"{staging} {mount_major_minor} {mount_source}\n",
                stderr="",
            )
        if command[0] == "findmnt" and "--target" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=f"{root_major_minor} {root_source}\n",
                stderr="",
            )
        if command[0] == "ssh-keygen":
            return SimpleNamespace(returncode=host_pin_status, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return run


def test_backup_config_fails_closed_without_encrypted_remote_prerequisites(backup_module):
    with pytest.raises(backup_module.BackupConfigurationError):
        backup_module.load_config({})


def test_runtime_prerequisites_reject_unmounted_staging_root(backup_module, tmp_path):
    config, staging = _runtime_config(backup_module, tmp_path)
    commands = []

    with pytest.raises(backup_module.BackupConfigurationError, match="dedicated encrypted staging mountpoint"):
        backup_module.validate_runtime_prerequisites(
            config,
            command_exists=lambda _: True,
            runner=_runtime_runner(staging, commands, mount_status=1),
        )


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

    ssh_command = backup_module.restic_sftp_command(config)
    restic_env = backup_module.restic_environment(
        config, base_env={"PATH": "/usr/bin", "SMTP_PASS": "not-forwarded"}
    )

    assert "StrictHostKeyChecking=yes" in ssh_command
    assert "UserKnownHostsFile=/etc/kfl-dms/secrets/known_hosts" in ssh_command
    assert "-i /etc/kfl-dms/secrets/backup-key" in ssh_command
    assert "backup@10.20.173.120" in ssh_command
    assert "-s sftp" in ssh_command
    assert "BatchMode=yes" in ssh_command
    assert "PasswordAuthentication=no" in ssh_command
    assert "KbdInteractiveAuthentication=no" in ssh_command
    assert "RESTIC_SFTP_COMMAND" not in restic_env
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
        "sha256:" + "a" * 64,
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
                stdout=json.dumps(
                    [
                        {
                            "id": "snapshot-123",
                            "tags": [
                                "dms-run-test",
                                "volume-kfl-aviation-dms-prod_dms_data",
                                "image-sha256-" + "a" * 64,
                            ],
                        }
                    ]
                ),
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    snapshot_id = backup_module.run_restic_backup(
        config,
        candidate,
        source_host="roc-app",
        source_image_id="sha256:" + "a" * 64,
        run_tag="dms-run-test",
        runner=fake_runner,
    )

    assert snapshot_id == "snapshot-123"
    commands = [" ".join(command) for command in calls]
    assert any(" backup " in f" {command} " for command in commands)
    assert any(" snapshots " in f" {command} " for command in commands)
    assert all("sftp.command=" in command for command in commands)
    assert all("StrictHostKeyChecking=yes" in command for command in commands)
    assert any("volume-kfl-aviation-dms-prod_dms_data" in command for command in commands)
    assert any("image-sha256-" + "a" * 64 in command for command in commands)
    assert not any(" forget " in f" {command} " or " prune " in f" {command} " for command in commands)


def test_restic_snapshot_confirmation_requires_volume_and_image_tags(backup_module, tmp_path):
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

    def fake_runner(command, **kwargs):
        stdout = json.dumps([{"id": "snapshot-123", "tags": ["dms-run-test"]}]) if "snapshots" in command else ""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    with pytest.raises(backup_module.BackupConfigurationError, match="did not confirm"):
        backup_module.run_restic_backup(
            config,
            candidate,
            source_host="roc-app",
            source_image_id="sha256:" + "a" * 64,
            run_tag="dms-run-test",
            runner=fake_runner,
        )


def test_runtime_prerequisites_reject_world_readable_repo_password_file(backup_module, tmp_path):
    config, staging = _runtime_config(backup_module, tmp_path, password_mode=0o644)
    commands = []

    with pytest.raises(backup_module.BackupConfigurationError, match="permissions"):
        backup_module.validate_runtime_prerequisites(
            config,
            command_exists=lambda _: True,
            runner=_runtime_runner(staging, commands),
        )


def test_runtime_prerequisites_accept_secure_files_with_pinned_host_key(backup_module, tmp_path):
    config, staging = _runtime_config(backup_module, tmp_path)
    commands = []

    backup_module.validate_runtime_prerequisites(
        config,
        command_exists=lambda _: True,
        runner=_runtime_runner(staging, commands),
    )

    assert commands[0][0] == "findmnt" and "--mountpoint" in commands[0]
    assert commands[1][0] == "findmnt" and "--target" in commands[1]
    assert commands[2] == ["ssh-keygen", "-F", "backup.example", "-f", str(config.ssh_known_hosts_file)]


def test_staging_encryption_attestation_must_match_mounted_device(backup_module, tmp_path):
    config, staging = _runtime_config(backup_module, tmp_path)
    attestation = json.loads(config.staging_attestation_file.read_text())
    attestation["source"] = "/dev/other-volume"
    config.staging_attestation_file.write_text(json.dumps(attestation))
    config.staging_attestation_file.chmod(0o600)
    commands = []

    with pytest.raises(backup_module.BackupConfigurationError, match="does not match"):
        backup_module.validate_runtime_prerequisites(
            config,
            command_exists=lambda _: True,
            runner=_runtime_runner(staging, commands),
        )


def test_staging_rejects_bind_mount_from_root_device(backup_module, tmp_path):
    config, staging = _runtime_config(backup_module, tmp_path)
    attestation = json.loads(config.staging_attestation_file.read_text())
    attestation["source"] = "/dev/sda1[/var/lib/kfl-aviation-dms-prod-backups/staging]"
    config.staging_attestation_file.write_text(json.dumps(attestation))
    config.staging_attestation_file.chmod(0o600)
    commands = []

    with pytest.raises(backup_module.BackupConfigurationError, match="different filesystem"):
        backup_module.validate_runtime_prerequisites(
            config,
            command_exists=lambda _: True,
            runner=_runtime_runner(
                staging,
                commands,
                mount_source="/dev/sda1[/var/lib/kfl-aviation-dms-prod-backups/staging]",
                mount_major_minor="8:1",
                root_source="/dev/sda1",
                root_major_minor="8:1",
            ),
        )


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
        "sha256:" + "a" * 64 + "\n",
    ]

    result = backup_module.discover_production_source(
        config,
        runner=lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=responses.pop(0),
            stderr="",
        ),
    )

    assert result == (source, "sha256:" + "a" * 64)


def test_backup_lock_rejects_overlapping_runs(tmp_path, backup_module):
    with backup_module.backup_lock(tmp_path):
        with pytest.raises(backup_module.BackupConfigurationError, match="already running"):
            with backup_module.backup_lock(tmp_path):
                pass


def test_backup_environment_parser_accepts_only_literal_backup_settings(tmp_path, backup_module):
    config_file = tmp_path / "backup.env"
    config_file.write_text(
        "DMS_BACKUP_VOLUME_NAME=kfl-aviation-dms-prod_dms_data\n"
        "DMS_BACKUP_STAGING_ATTESTATION_FILE=/etc/kfl-aviation-dms-prod/backup-secrets/staging-encryption.json\n"
    )

    parsed = backup_module.read_backup_environment(config_file, inherited={})

    assert parsed["DMS_BACKUP_VOLUME_NAME"] == "kfl-aviation-dms-prod_dms_data"
    assert parsed["DMS_BACKUP_STAGING_ATTESTATION_FILE"] == "/etc/kfl-aviation-dms-prod/backup-secrets/staging-encryption.json"

    config_file.write_text("SMTP_PASS=not-a-real-secret\n")
    with pytest.raises(backup_module.BackupConfigurationError, match="unsupported"):
        backup_module.read_backup_environment(config_file, inherited={})


def test_backup_environment_requires_file_and_overrides_inherited_backup_values(tmp_path, backup_module):
    config_file = tmp_path / "missing-backup.env"
    inherited = {"PATH": "/usr/bin", "DMS_BACKUP_STAGING_ROOT": "/untrusted/inherited"}

    with pytest.raises(backup_module.BackupConfigurationError, match="configuration file"):
        backup_module.read_backup_environment(config_file, inherited=inherited)

    config_file.write_text("DMS_BACKUP_STAGING_ROOT=/trusted/configured\n")
    config_file.chmod(0o600)
    parsed = backup_module.read_backup_environment(config_file, inherited=inherited)

    assert parsed["PATH"] == "/usr/bin"
    assert parsed["DMS_BACKUP_STAGING_ROOT"] == "/trusted/configured"
