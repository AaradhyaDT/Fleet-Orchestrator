"""
Windows Credential Manager integration via advapi32.dll.
Provides sub-millisecond snapshotting and restoration of generic credentials,
enabling true multi-account profile swapping for Google Antigravity (gemini:antigravity).
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

AGY_CREDENTIAL_TARGET = "gemini:antigravity"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


class CREDENTIAL_ATTRIBUTE(ctypes.Structure):
    _fields_ = [
        ("Keyword", wintypes.LPWSTR),
        ("Flags", wintypes.DWORD),
        ("ValueSize", wintypes.DWORD),
        ("Value", ctypes.POINTER(ctypes.c_byte)),
    ]


class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def is_windows() -> bool:
    return os.name == "nt"


def read_generic_credential(target_name: str = AGY_CREDENTIAL_TARGET) -> Optional[Tuple[str, bytes, int]]:
    """Reads a generic credential from Windows Credential Manager.

    Returns:
        (username, credential_blob, persist_type) or None if not found / non-Windows.
    """
    if not is_windows():
        logger.debug("Windows Credential Manager is only available on NT platforms.")
        return None

    advapi32 = ctypes.windll.advapi32
    pcred = ctypes.POINTER(CREDENTIAL)()

    if not advapi32.CredReadW(target_name, CRED_TYPE_GENERIC, 0, ctypes.byref(pcred)):
        err = ctypes.GetLastError()
        logger.debug("CredReadW for '%s' failed with error code %d", target_name, err)
        return None

    try:
        cred = pcred.contents
        blob = bytes(cred.CredentialBlob[: cred.CredentialBlobSize])
        user = cred.UserName or ""
        persist = cred.Persist
        return user, blob, persist
    finally:
        advapi32.CredFree(pcred)


def write_generic_credential(
    target_name: str = AGY_CREDENTIAL_TARGET,
    user_name: str = "antigravity",
    blob: bytes = b"",
    persist: int = CRED_PERSIST_LOCAL_MACHINE,
) -> bool:
    """Writes a generic credential to Windows Credential Manager."""
    if not is_windows():
        return False

    advapi32 = ctypes.windll.advapi32
    raw_blob = (ctypes.c_byte * len(blob)).from_buffer_copy(blob)

    cred = CREDENTIAL()
    cred.Flags = 0
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = target_name
    cred.Comment = None
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = ctypes.cast(raw_blob, ctypes.POINTER(ctypes.c_byte))
    cred.Persist = persist
    cred.AttributeCount = 0
    cred.Attributes = None
    cred.TargetAlias = None
    cred.UserName = user_name

    res = advapi32.CredWriteW(ctypes.byref(cred), 0)
    if not res:
        err = ctypes.GetLastError()
        logger.error("CredWriteW for '%s' failed with error code %d", target_name, err)
        return False
    return True


def delete_generic_credential(target_name: str = AGY_CREDENTIAL_TARGET) -> bool:
    """Deletes a generic credential from Windows Credential Manager."""
    if not is_windows():
        return False

    advapi32 = ctypes.windll.advapi32
    res = advapi32.CredDeleteW(target_name, CRED_TYPE_GENERIC, 0)
    return bool(res)


def snapshot_agy_credential(output_file: Path) -> bool:
    """Snapshots the active gemini:antigravity credential to a binary file."""
    cred = read_generic_credential(AGY_CREDENTIAL_TARGET)
    if not cred:
        return False

    user_name, blob, persist = cred
    output_path = Path(output_file).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Simple binary structure: length of username (4 bytes) + username UTF-8 + persist (4 bytes) + blob
    user_bytes = user_name.encode("utf-8")
    with open(output_path, "wb") as f:
        f.write(len(user_bytes).to_bytes(4, "little"))
        f.write(user_bytes)
        f.write(persist.to_bytes(4, "little"))
        f.write(blob)
    return True


def restore_agy_credential(input_file: Path) -> bool:
    """Restores a snapshotted credential binary into Windows Credential Manager as gemini:antigravity."""
    input_path = Path(input_file).expanduser().resolve()
    if not input_path.exists():
        logger.error("Credential snapshot file does not exist: %s", input_path)
        return False

    with open(input_path, "rb") as f:
        user_len = int.from_bytes(f.read(4), "little")
        user_name = f.read(user_len).decode("utf-8")
        persist = int.from_bytes(f.read(4), "little")
        blob = f.read()

    return write_generic_credential(
        target_name=AGY_CREDENTIAL_TARGET,
        user_name=user_name,
        blob=blob,
        persist=persist,
    )
