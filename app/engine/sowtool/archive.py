"""Reads files out of the game's .arch06 archives (LTAR version 4).

Header: 'LTAR', version, name table size, folder count, file count; the name table starts at 0x30.
File entries (30 bytes): name offset u32, data offset u64, stored size u64, unpacked size u64, flags u16.
Folder entries (16 bytes): name offset (full path), first subfolder, next folder, file count; files belong
to folders in folder order. Stored data is a run of chunks: stored size u32, unpacked size u32, data,
each chunk aligned to 4 bytes from the start of the file. Compressed chunks are Oodle (Kraken).

Oodle: on Windows the game's own oo2core_5_win64.dll is used; elsewhere a library exporting
ooz_decompress(src, src_len, dst, dst_len) given by the OOZ_LIB environment variable.
"""
import ctypes
import os
import struct


class Archive:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            head = f.read(0x30)
            magic, version, name_size, folder_count, file_count = struct.unpack_from('<4s4I', head)
            if magic != b'LTAR':
                raise ValueError('%s: not an LTAR archive' % path)
            names = f.read(name_size)
            raw_files = f.read(30 * file_count)
            raw_folders = f.read(16 * folder_count)

        def name(o):
            return names[o:names.index(b'\0', o)].decode('latin1')

        files = [struct.unpack_from('<IQQQH', raw_files, 30 * i) for i in range(file_count)]
        self.files = {}
        k = 0
        for i in range(folder_count):
            folder, _, _, count = struct.unpack_from('<4I', raw_folders, 16 * i)
            folder = name(folder)
            for _ in range(count):
                if k >= file_count:
                    break
                n, off, stored, size, _ = files[k]
                path = folder + '\\' + name(n) if folder else name(n)
                self.files[path.lower()] = (off, stored, size)
                k += 1

    def read(self, path, oodle):
        off, stored, size = self.files[path.lower()]
        with open(self.path, 'rb') as f:
            f.seek(off)
            data = f.read(stored)
        if stored == size:
            return data
        out, p = bytearray(), 0
        while p < stored:
            cs, us = struct.unpack_from('<II', data, p)
            chunk = data[p + 8:p + 8 + cs]
            out += chunk if cs == us else oodle(chunk, us)
            p = (p + 8 + cs + 3) & ~3
        if len(out) != size:
            raise ValueError('%s: unpacked %d bytes, expected %d' % (path, len(out), size))
        return bytes(out)


def oodle_for(game_dir=None):
    """A function (compressed bytes, unpacked size) -> bytes."""
    dll = None
    if game_dir:
        for root, _, names in os.walk(game_dir):
            if 'oo2core_5_win64.dll' in (n.lower() for n in names):
                dll = os.path.join(root, 'oo2core_5_win64.dll')
                break
    if dll and os.name == 'nt':
        lib = ctypes.WinDLL(dll)
        fn = lib.OodleLZ_Decompress
        fn.restype = ctypes.c_int64
        fn.argtypes = [ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_int64, ctypes.c_int]

        def run(src, size):
            buf = ctypes.create_string_buffer(size + 64)
            n = fn(src, len(src), buf, size, 1, 0, 0, None, 0, None, None, None, 0, 3)
            if n != size:
                raise ValueError('Oodle failed (%d of %d bytes)' % (n, size))
            return buf.raw[:size]
        return run
    lib = ctypes.CDLL(os.environ.get('OOZ_LIB', 'libooz.so'))

    def run(src, size):
        buf = ctypes.create_string_buffer(size + 64)
        n = lib.ooz_decompress(src, len(src), buf, size)
        if n != size:
            raise ValueError('ooz failed (%d of %d bytes)' % (n, size))
        return buf.raw[:size]
    return run


# Newest archive first: later patches override earlier ones.
WANTED = {
    'game.gamedb': (['hotchunk.arch06'], 'database\\game\\game.gamedb'),
    'string_ruru.strdb': (['hotchunk.arch06'], 'database\\string\\ruru\\string.strdb'),
}


def extract(game_dir, out_dir, log=print):
    """Copies the database and the Russian texts from the game folder into out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    archives = {}
    for root, _, names in os.walk(game_dir):
        for n in names:
            if n.lower().endswith('.arch06'):
                archives.setdefault(n.lower(), os.path.join(root, n))
    oodle = oodle_for(game_dir)
    for out_name, (arch_names, inner) in WANTED.items():
        for a in arch_names:
            if a in archives:
                data = Archive(archives[a]).read(inner, oodle)
                with open(os.path.join(out_dir, out_name), 'wb') as f:
                    f.write(data)
                log('%s <- %s (%d bytes)' % (out_name, a, len(data)))
                break
        else:
            raise FileNotFoundError('%s not found in %s' % (inner, game_dir))
