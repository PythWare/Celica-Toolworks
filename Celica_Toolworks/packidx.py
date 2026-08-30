from __future__ import annotations
import struct
from pathlib import Path

MAGIC_ENDILTLE = b"ENDILTLE"
MAGIC_PACKHEDR = b"PACKHEDR"
MAGIC_PACKTOC = b"PACKTOC "
MAGIC_PACKFSLS = b"PACKFSLS"
MAGIC_PACKFSHD = b"PACKFSHD"
MAGIC_GENESTRT = b"GENESTRT"
NODE_DIR = 1
NODE_FILE = 512
TOC_ENTRY_SIZE = 40
FSLS_ENTRY_SIZE = 40
FSHD_ENTRY_SIZE = 32
ARCHIVE_NAMES = (
    "data.apk",
    "data_rom.apk",
    "motion.apk",
    "unit.apk",
    "weapon.apk",
)
EXE_NAME = "SAOLS.exe"
DATA_DIR_NAME = "data"

class PackIndexError(Exception):
    pass

class PackFile:
    __slots__ = ("path", "archive", "offset", "stored_size", "real_size")

    def __init__(self, path, archive, offset, stored_size, real_size):
        self.path = path
        self.archive = archive
        self.offset = offset
        self.stored_size = stored_size
        self.real_size = real_size

    @property
    def compressed(self):
        return self.stored_size != self.real_size

    def as_tuple(self):
        return (self.path, self.archive, self.offset, self.stored_size, self.real_size)

class ArchiveIndex:
    def __init__(self, archive_name, files):
        self.archive_name = archive_name
        self.files = files

    @property
    def total_stored(self):
        return sum(item.stored_size for item in self.files)

    @property
    def total_real(self):
        return sum(item.real_size for item in self.files)

def read_string_table(buf, base):
    count = struct.unpack_from("<I", buf, base + 0x10)[0]
    data_offset = struct.unpack_from("<I", buf, base + 0x18)[0]
    table = base + 0x20
    strings_at = base + 0x10 + data_offset

    if count <= 0 or count > 2_000_000:
        raise PackIndexError(f"implausible GENESTRT count {count}")

    offsets = struct.unpack_from(f"<{count}I", buf, table)
    out = []
    for value in offsets:
        start = strings_at + value
        end = buf.find(b"\x00", start)
        if end < 0:
            raise PackIndexError("unterminated GENESTRT string")
        out.append(buf[start:end].decode("latin1"))
    return out

def parse_flat(buf, archive, toc_at, strings):
    entry_size = struct.unpack_from("<I", buf, toc_at + 0x10)[0]
    node_count = struct.unpack_from("<I", buf, toc_at + 0x14)[0]
    nodes_at = toc_at + 0x20

    if entry_size != TOC_ENTRY_SIZE:
        raise PackIndexError(f"unexpected TOC entry size {entry_size}")

    string_count = len(strings)
    files = []
    stack = [(0, "")]
    seen = set()

    while stack:
        index, prefix = stack.pop()
        if index >= node_count or index in seen:
            continue
        seen.add(index)

        offset = nodes_at + index * TOC_ENTRY_SIZE
        kind, name_index = struct.unpack_from("<II", buf, offset)
        if name_index >= string_count:
            continue

        name = strings[name_index]
        full = f"{prefix}/{name}" if prefix and name else (prefix or name)

        if kind == NODE_DIR:
            child_start, child_count = struct.unpack_from("<II", buf, offset + 0x10)
            if child_count and child_start + child_count <= node_count:
                for child in range(child_start, child_start + child_count):
                    stack.append((child, full))
        elif kind == NODE_FILE:
            data_offset = struct.unpack_from("<Q", buf, offset + 0x10)[0]
            real_size = struct.unpack_from("<Q", buf, offset + 0x18)[0]
            stored_size = struct.unpack_from("<Q", buf, offset + 0x20)[0]
            files.append(PackFile(full, archive, data_offset, stored_size, real_size))

    return files

def parse_group(buf, archive, base, limit):
    if buf[base:base + 8] != MAGIC_ENDILTLE:
        return []
    if buf[base + 0x10:base + 0x18] != MAGIC_PACKFSHD:
        return []

    table_size = struct.unpack_from("<Q", buf, base + 0x18)[0]
    count = struct.unpack_from("<I", buf, base + 0x28)[0]
    entries_at = base + 0x40

    if count <= 0 or count > 500_000:
        return []

    strings_at = buf.find(MAGIC_GENESTRT, base + 0x10 + table_size, limit)
    if strings_at < 0:
        return []

    strings = read_string_table(buf, strings_at)

    files = []
    for i in range(count):
        offset = entries_at + i * FSHD_ENTRY_SIZE
        entry_id = struct.unpack_from("<I", buf, offset)[0]
        data_offset = struct.unpack_from("<Q", buf, offset + 0x08)[0]
        real_size = struct.unpack_from("<Q", buf, offset + 0x10)[0]
        stored_size = struct.unpack_from("<Q", buf, offset + 0x18)[0]

        if entry_id >= len(strings):
            continue

        files.append(
            PackFile(strings[entry_id], archive, base + data_offset, stored_size, real_size)
        )

    return files

def parse_grouped(buf, archive, fsls_at):
    count = struct.unpack_from("<I", buf, fsls_at + 0x10)[0]
    entry_size = struct.unpack_from("<I", buf, fsls_at + 0x14)[0]
    entries_at = fsls_at + 0x20

    if entry_size != FSLS_ENTRY_SIZE:
        raise PackIndexError(f"unexpected PACKFSLS entry size {entry_size}")

    files = []
    for i in range(count):
        offset = entries_at + i * FSLS_ENTRY_SIZE
        group_offset = struct.unpack_from("<Q", buf, offset + 0x08)[0]
        group_size = struct.unpack_from("<Q", buf, offset + 0x10)[0]
        if group_offset + group_size > len(buf):
            continue
        files.extend(parse_group(buf, archive, group_offset, group_offset + group_size))

    return files

def load_archive(archive_path, archive_index=0):
    archive_path = Path(archive_path)
    buf = archive_path.read_bytes()

    if not buf.startswith(MAGIC_ENDILTLE):
        raise PackIndexError(f"{archive_path.name}: missing ENDILTLE signature")

    fsls_at = buf.find(MAGIC_PACKFSLS, 0, 0x10000)
    toc_at = buf.find(MAGIC_PACKTOC, 0, 0x10000)

    if fsls_at >= 0:
        files = parse_grouped(buf, archive_index, fsls_at)
        if files:
            return ArchiveIndex(archive_path.name, files)

    if toc_at >= 0:
        strings_at = buf.find(MAGIC_GENESTRT)
        if strings_at < 0:
            raise PackIndexError(f"{archive_path.name}: no GENESTRT")
        strings = read_string_table(buf, strings_at)
        files = parse_flat(buf, archive_index, toc_at, strings)
        return ArchiveIndex(archive_path.name, files)

    raise PackIndexError(f"{archive_path.name}: no PACKTOC or PACKFSLS")

def archive_dir_for(game_root):
    game_root = Path(game_root)
    for candidate in (game_root / DATA_DIR_NAME, game_root):
        if any((candidate / name).is_file() for name in ARCHIVE_NAMES):
            return candidate
    return None

def resolve_game_root(selected):
    selected = Path(selected).resolve()
    parent = selected.parent

    if (selected / EXE_NAME).is_file():
        return selected

    if selected.name.lower() == DATA_DIR_NAME and archive_dir_for(parent) is not None:
        return parent

    if any((selected / name).is_file() for name in ARCHIVE_NAMES):
        return selected

    if archive_dir_for(selected) is not None:
        return selected

    if (parent / EXE_NAME).is_file():
        return parent

    return selected

def discover_archives(game_dir):
    archive_dir = archive_dir_for(resolve_game_root(game_dir))
    if archive_dir is None:
        return []

    found = []
    for index, name in enumerate(ARCHIVE_NAMES):
        candidate = archive_dir / name
        if candidate.is_file():
            found.append((index, candidate))
    return found


def load_all(game_dir):
    indexes = []
    for index, path in discover_archives(game_dir):
        indexes.append(load_archive(path, index))
    return indexes
