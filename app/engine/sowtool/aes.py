"""AES-256-CBC without padding: Windows CNG (bcrypt.dll) on Windows, the 'cryptography' package elsewhere."""
import ctypes
import os

if os.name == 'nt':
    _bc = ctypes.WinDLL('bcrypt')
    _ULONG = ctypes.c_ulong

    def _check(status, what):
        if status:
            raise OSError('%s failed: 0x%08x' % (what, status & 0xFFFFFFFF))

    def _run(key, iv, data, encrypt):
        alg, hkey = ctypes.c_void_p(), ctypes.c_void_p()
        _check(_bc.BCryptOpenAlgorithmProvider(ctypes.byref(alg), ctypes.c_wchar_p('AES'), None, 0),
               'BCryptOpenAlgorithmProvider')
        try:
            mode = ctypes.create_unicode_buffer('ChainingModeCBC')
            _check(_bc.BCryptSetProperty(alg, ctypes.c_wchar_p('ChainingMode'), mode, ctypes.sizeof(mode), 0),
                   'BCryptSetProperty')
            _check(_bc.BCryptGenerateSymmetricKey(alg, ctypes.byref(hkey), None, 0, key, len(key), 0),
                   'BCryptGenerateSymmetricKey')
            try:
                ivbuf = ctypes.create_string_buffer(bytes(iv), len(iv))
                out = ctypes.create_string_buffer(len(data))
                done = _ULONG()
                fn = _bc.BCryptEncrypt if encrypt else _bc.BCryptDecrypt
                _check(fn(hkey, data, len(data), None, ivbuf, len(iv), out, len(data), ctypes.byref(done), 0),
                       'BCryptEncrypt' if encrypt else 'BCryptDecrypt')
                return out.raw[:done.value]
            finally:
                _bc.BCryptDestroyKey(hkey)
        finally:
            _bc.BCryptCloseAlgorithmProvider(alg, 0)

    def cbc_decrypt(key, iv, data):
        return _run(key, iv, data, False)

    def cbc_encrypt(key, iv, data):
        return _run(key, iv, data, True)
else:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    def cbc_decrypt(key, iv, data):
        d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return d.update(data) + d.finalize()

    def cbc_encrypt(key, iv, data):
        e = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return e.update(data) + e.finalize()
