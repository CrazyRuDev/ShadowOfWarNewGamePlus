"""Shadow of War save file (SOM2/SOM3) decryption and encryption.

Format, as read and written by ShadowOfWar.exe 1.0.8874.0
(load: 0x14119A3FD, save: 0x14052B1CC):

    header, 16 bytes, little endian:
        magic       'SOM3' (or older 'SOM2')
        crc32       CRC32 of the decrypted data
        enc_size    size of the encrypted data that follows
        plain_size  size of the decrypted data
    data: AES-256-CBC, PKCS#7 padding

The key is a fixed 32-byte string from the exe with the 4 CRC32 bytes and, for SOM3,
the 4 bytes of the user id written into fixed positions. The IV is a fixed string.
The user id is the hex prefix of the save file name (096c2a9f_ShadowOfWar.sav -> 0x096c2a9f).

usage:
    python3 sowsave.py decrypt <save.sav> <out.bin>
    python3 sowsave.py encrypt <in.bin> <user id hex> <save.sav>
"""
import os
import struct
import sys
import zlib

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY_TEMPLATE = b"ad@210766@vac94Cd_?dVt5$alivjz$e"
IV = b"yuwgb@oftv@gx$t3"
CRC_POS = (0x1A, 0x0B, 0x12, 0x11)     # positions of crc32 bytes 0..3 in the key
USER_POS = (0x0A, 0x1E, 0x16, 0x02)    # positions of user id bytes 0..3 (SOM3 only)


def user_id_from_name(path):
    return int(os.path.basename(path).split("_", 1)[0], 16)


def make_key(crc, user_id):
    key = bytearray(KEY_TEMPLATE)
    for i, pos in enumerate(CRC_POS):
        key[pos] = (crc >> (8 * i)) & 0xFF
    if user_id is not None:
        for i, pos in enumerate(USER_POS):
            key[pos] = (user_id >> (8 * i)) & 0xFF
    return bytes(key)


def decrypt(data, user_id):
    magic, crc, enc_size, plain_size = struct.unpack_from("<4sIII", data)
    if magic not in (b"SOM2", b"SOM3"):
        raise ValueError("not a Shadow of War save: magic %r" % magic)
    key = make_key(crc, user_id if magic == b"SOM3" else None)
    dec = Cipher(algorithms.AES(key), modes.CBC(IV)).decryptor()
    padded = dec.update(data[16:16 + enc_size]) + dec.finalize()
    unpad = padding.PKCS7(128).unpadder()
    try:
        plain = unpad.update(padded) + unpad.finalize()
    except ValueError:
        raise ValueError("wrong user id (bad padding)")
    if len(plain) != plain_size or zlib.crc32(plain) != crc:
        raise ValueError("wrong user id (size/crc mismatch)")
    return plain


def encrypt(plain, user_id):
    crc = zlib.crc32(plain)
    pad = padding.PKCS7(128).padder()
    padded = pad.update(plain) + pad.finalize()
    enc = Cipher(algorithms.AES(make_key(crc, user_id)), modes.CBC(IV)).encryptor()
    body = enc.update(padded) + enc.finalize()
    return struct.pack("<4sIII", b"SOM3", crc, len(body), len(plain)) + body


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "decrypt":
        plain = decrypt(open(sys.argv[2], "rb").read(), user_id_from_name(sys.argv[2]))
        open(sys.argv[3], "wb").write(plain)
        print("decrypted %d bytes -> %s" % (len(plain), sys.argv[3]))
    elif len(sys.argv) == 5 and sys.argv[1] == "encrypt":
        out = encrypt(open(sys.argv[2], "rb").read(), int(sys.argv[3], 16))
        open(sys.argv[4], "wb").write(out)
        print("encrypted %d bytes -> %s" % (len(out), sys.argv[4]))
    else:
        sys.exit(__doc__)
