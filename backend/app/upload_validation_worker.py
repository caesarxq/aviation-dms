"""Minimal stdin/stdout file parser for upload_validation.py; never writes source bytes."""
from __future__ import annotations

import sys
import os
import pwd
import resource
from io import BytesIO


def _limit(resource_name: int, soft_limit: int, hard_limit: int) -> tuple[int, int]:
    current_soft, current_hard = resource.getrlimit(resource_name)
    capped_hard = hard_limit if current_hard == resource.RLIM_INFINITY else min(hard_limit, current_hard)
    capped_soft = soft_limit if current_soft == resource.RLIM_INFINITY else min(soft_limit, current_soft)
    return min(capped_soft, capped_hard), capped_hard


def _apply_worker_restrictions() -> None:
    """Reduce parser CPU, memory where supported, file-write and descriptor limits."""
    limits = [
        (resource.RLIMIT_CPU, 5, 6),
        (resource.RLIMIT_FSIZE, 0, 0),
        (resource.RLIMIT_NOFILE, 16, 16),
        (resource.RLIMIT_CORE, 0, 0),
    ]
    if sys.platform.startswith("linux"):
        limits.append((resource.RLIMIT_AS, 512 * 1024 * 1024, 512 * 1024 * 1024))
    for resource_name, soft_limit, hard_limit in limits:
        resource.setrlimit(resource_name, _limit(resource_name, soft_limit, hard_limit))
    os.umask(0o077)

    if os.geteuid() == 0:
        unprivileged = pwd.getpwnam("nobody")
        os.setgroups([])
        os.setgid(unprivileged.pw_gid)
        os.setuid(unprivileged.pw_uid)

    if sys.platform.startswith("linux"):
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            error_number = ctypes.get_errno()
            raise OSError(error_number, "could not set parser no_new_privs")


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    extension = sys.argv[1].lower()
    try:
        max_bytes = int(sys.argv[2])
        max_image_pixels = int(sys.argv[3])
    except ValueError:
        return 2
    if max_bytes < 1 or max_image_pixels < 1:
        return 2
    try:
        _apply_worker_restrictions()
    except Exception:
        return 2

    content = sys.stdin.buffer.read(max_bytes + 1)
    if len(content) > max_bytes:
        return 1

    try:
        if extension == ".pdf":
            from pypdf import PdfReader

            if not content.startswith(b"%PDF-"):
                return 1
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted or len(reader.pages) < 1:
                return 1
            return 0

        if extension in {".png", ".jpg", ".jpeg"}:
            from PIL import Image

            expected_format = "PNG" if extension == ".png" else "JPEG"
            with Image.open(BytesIO(content)) as image:
                if image.format != expected_format:
                    return 1
                if image.width < 1 or image.height < 1 or image.width * image.height > max_image_pixels:
                    return 1
                image.verify()
            with Image.open(BytesIO(content)) as decoded_image:
                if decoded_image.format != expected_format:
                    return 1
                decoded_image.load()
            return 0
    except Exception:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
