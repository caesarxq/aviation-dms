"""H1 regression: production deployment must be fail-closed on the pre-deploy backup.

deploy-prod.sh must abort (non-zero, before any docker command) when the backup
script is missing or fails, and only proceed when a backup succeeds. These tests
run the real script with stubbed sudo/docker so nothing is actually deployed.
"""
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy-prod.sh"


def _run_deploy(tmp_path, backup_script: Path | None, health_status: str = "healthy"):
    """Run deploy-prod.sh with stubbed sudo/docker; return (returncode, log, output)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "stub.log"
    log.write_text("")

    # sudo stub: record the invocation, then actually exec the command so the
    # backup script's real exit code propagates (docker itself is stubbed below).
    sudo = bin_dir / "sudo"
    sudo.write_text("#!/bin/bash\necho \"sudo $*\" >> \"$STUB_LOG\"\nexec \"$@\"\n")
    sudo.chmod(0o755)

    # docker stub: record and no-op (never touch a real daemon).
    docker = bin_dir / "docker"
    docker.write_text("#!/bin/bash\necho \"docker $*\" >> \"$STUB_LOG\"\nif [[ $1 == inspect ]]; then echo \"$DOCKER_HEALTH_STATUS\"; fi\nexit 0\n")
    docker.chmod(0o755)

    sleeper = bin_dir / "sleep"
    sleeper.write_text("#!/bin/bash\nexit 0\n")
    sleeper.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["STUB_LOG"] = str(log)
    env["DOCKER_HEALTH_STATUS"] = health_status
    env["PROD_DIR"] = str(tmp_path)
    if backup_script is not None:
        env["BACKUP_SCRIPT"] = str(backup_script)
    else:
        env["BACKUP_SCRIPT"] = str(tmp_path / "does-not-exist-backup.sh")

    proc = subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), "test-image-tag"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    return proc.returncode, log.read_text(), proc.stdout + proc.stderr


def test_missing_backup_script_aborts_before_any_docker_command(tmp_path):
    code, log, output = _run_deploy(tmp_path, backup_script=None)
    assert code != 0, "deploy must abort when the backup script is missing"
    assert "docker" not in log, "no docker command may run without a backup"
    assert "backup" in output.lower()


def test_failing_backup_aborts_before_any_docker_command(tmp_path):
    backup = tmp_path / "backup.sh"
    backup.write_text("#!/bin/bash\nexit 1\n")
    backup.chmod(0o755)
    code, log, output = _run_deploy(tmp_path, backup_script=backup)
    assert code != 0, "deploy must abort when the backup fails"
    assert "docker" not in log, "no docker command may run after a failed backup"


def test_successful_backup_allows_deployment_to_proceed(tmp_path):
    backup = tmp_path / "backup.sh"
    backup.write_text("#!/bin/bash\nexit 0\n")
    backup.chmod(0o755)
    code, log, output = _run_deploy(tmp_path, backup_script=backup)
    # A successful backup must not block deployment: docker commands are reached.
    assert "docker" in log, "deployment should proceed after a successful backup"


def test_health_failure_does_not_bring_down_production_services(tmp_path):
    backup = tmp_path / "backup.sh"
    backup.write_text("#!/bin/bash\nexit 0\n")
    backup.chmod(0o755)
    code, log, output = _run_deploy(tmp_path, backup_script=backup, health_status="unhealthy")

    assert code != 0
    assert "docker compose" in log
    assert "docker compose down" not in log