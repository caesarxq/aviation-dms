#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${DMS_BACKUP_PYTHON:-/usr/bin/python3}"
exec "${PYTHON_BIN}" "${SCRIPT_DIR}/full_stack_backup_prod.py" "$@"
