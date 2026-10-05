"""DPAPI CurrentUser state, never plaintext credentials on disk."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def transform(value, decrypt=False):
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    library = ctypes.WinDLL('crypt32', use_last_error=True)
    function = library.CryptUnprotectData if decrypt else library.CryptProtectData
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError('PRIVATE_STATE_UNAVAILABLE')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.WinDLL('kernel32').LocalFree(target.data)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    temporary.write_bytes(transform(json.dumps(value).encode()))
    temporary.replace(path)


def read(path):
    return json.loads(transform(Path(path).read_bytes(), decrypt=True))
