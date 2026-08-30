from __future__ import annotations
import shutil, subprocess
from pathlib import Path
from . import packidx

EXE_NAME = "SAOLS.exe"
PROXY_NAME = "d3dcompiler_47.dll"
REAL_NAME = "backup_vanilla.dll"
LOG_NAME = "sao_loader.log"
VERBOSE_NAME = "sao_loader_verbose.txt"
DATA_DIR = "data"
LOADER_DIR = Path(__file__).resolve().parent / "Loader"
LOADER_SOURCE = LOADER_DIR / "loader.c"
LOADER_DEF = LOADER_DIR / "loader.def"
LOADER_BUILT = LOADER_DIR / PROXY_NAME
LOADER_MARKER = b"sao_loader.log"
GCC_CANDIDATES = (
    r"C:\msys64\ucrt64\bin\gcc.exe",
    r"C:\msys64\mingw64\bin\gcc.exe",
    "gcc",
)
class PatchError(Exception):
    pass

def find_game_files(game_dir):
    root = packidx.resolve_game_root(game_dir)
    archive_dir = packidx.archive_dir_for(root)
    archives = [path.name for _, path in packidx.discover_archives(root)]
    return {
        "dir": root,
        "archive_dir": archive_dir,
        "exe": root / EXE_NAME if (root / EXE_NAME).is_file() else None,
        "archives": archives,
        "proxy": root / PROXY_NAME,
        "real": root / REAL_NAME,
        "data": root / DATA_DIR,
    }

def is_our_loader(path):
    path = Path(path)
    if not path.is_file():
        return False
    if path.stat().st_size > 1_000_000:
        return False
    try:
        return LOADER_MARKER in path.read_bytes()
    except OSError:
        return False

def resolve_gcc():
    for candidate in GCC_CANDIDATES:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    return None

def build_loader(force=False):
    if LOADER_BUILT.is_file() and not force:
        if LOADER_SOURCE.stat().st_mtime <= LOADER_BUILT.stat().st_mtime:
            return LOADER_BUILT

    compiler = resolve_gcc()
    if compiler is None:
        if LOADER_BUILT.is_file():
            return LOADER_BUILT
        raise PatchError("No gcc found and no prebuilt loader is present.")

    command = [
        compiler,
        "-O2",
        "-shared",
        "-s",
        "-o",
        str(LOADER_BUILT),
        str(LOADER_SOURCE),
        str(LOADER_DEF),
        "-lkernel32",
        "-static-libgcc",
        "-Wl,--strip-all",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=str(LOADER_DIR),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    if result.returncode != 0:
        raise PatchError(f"Loader build failed:\n{result.stderr.strip()[:800]}")

    if not LOADER_BUILT.is_file():
        raise PatchError("Loader build reported success but produced no dll.")

    return LOADER_BUILT

def status(game_dir):
    found = find_game_files(game_dir)
    lines = []

    if found["exe"] is None:
        lines.append("SAOLS.exe: Missing")
    lines.append(f"Containers: {len(found['archives'])}")

    proxy = found["proxy"]
    real = found["real"]

    if is_our_loader(proxy):
        if real.is_file():
            lines.append("Loader: installed")
        else:
            lines.append("Loader: installed, vanilla dll missing")
    elif proxy.is_file():
        lines.append("Loader: not installed")
    else:
        lines.append(f"Loader: not installed, {PROXY_NAME} missing")

    extracted = extracted_dirs(found["dir"])
    if extracted:
        lines.append(f"Extracted: {len(extracted)} folders in data")
    else:
        lines.append("Extracted: nothing yet")

    if (found["dir"] / VERBOSE_NAME).is_file():
        lines.append("Verbose loader logging: on")

    return lines

def index_subdirs(game_dir):
    names = set()
    for index, path in packidx.discover_archives(game_dir):
        for item in packidx.load_archive(path, index).files:
            parts = item.path.split("/")
            if len(parts) >= 3 and parts[0].lower() == DATA_DIR:
                names.add(parts[1])
    return names

def extracted_dirs(game_root):
    data_dir = Path(game_root) / DATA_DIR
    if not data_dir.is_dir():
        return []
    known = index_subdirs(game_root)
    return [child for child in data_dir.iterdir()
            if child.is_dir() and child.name in known]

def remove_extracted(game_dir):
    root = packidx.resolve_game_root(game_dir)
    targets = extracted_dirs(root)
    lines = []

    if not targets:
        lines.append("Nothing to remove, no extracted subfolders found.")
        return lines

    removed = 0
    for target in targets:
        try:
            shutil.rmtree(target)
            removed += 1
        except OSError as exc:
            lines.append(f"Failed {target.name}: {exc}")

    lines.append(f"Removed {removed} of {len(targets)} extracted folders.")
    return lines

def install(game_dir):
    found = find_game_files(game_dir)
    lines = []

    if found["exe"] is None:
        raise PatchError(f"{EXE_NAME} not found in {found['dir']}")

    proxy = found["proxy"]
    real = found["real"]

    if not is_our_loader(proxy) and not proxy.is_file():
        raise PatchError(
            f"{PROXY_NAME} is missing from the game folder. "
            "The loader replaces that file and needs the vanilla copy to forward to."
        )

    built = build_loader()

    if not is_our_loader(proxy):
        if real.is_file():
            raise PatchError(
                f"{REAL_NAME} already exists but {PROXY_NAME} is the vanilla dll. "
                "Resolve that so nothing gets overwritten."
            )
        shutil.move(str(proxy), str(real))

    if not real.is_file():
        raise PatchError(f"{REAL_NAME} is missing, skipping.")

    shutil.copy2(str(built), str(proxy))
    lines.append(f"Loader installed. Vanilla dll kept as {REAL_NAME}.")

    return lines

def remove(game_dir):
    found = find_game_files(game_dir)
    lines = []

    proxy = found["proxy"]
    real = found["real"]

    if not is_our_loader(proxy):
        if proxy.is_file():
            lines.append("Loader wasnt installed.")
            return lines
        if real.is_file():
            shutil.move(str(real), str(proxy))
            lines.append(f"Restored {PROXY_NAME} from {REAL_NAME}")
            return lines
        raise PatchError(f"Neither {PROXY_NAME} nor {REAL_NAME} is present.")

    if not real.is_file():
        raise PatchError(
            f"{REAL_NAME} is missing. Removing the loader now would leave the game "
            "with no d3dcompiler. Restore that file from your backup first."
        )

    proxy.unlink()
    shutil.move(str(real), str(proxy))
    lines.append("Loader removed, vanilla dll restored.")

    return lines
