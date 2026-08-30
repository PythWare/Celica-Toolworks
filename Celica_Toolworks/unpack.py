from __future__ import annotations
import os, time, zlib
from zlib import MAX_WBITS
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import packidx

CHUNK_SIZE = 200
MIN_WORKERS = 2
MAX_WORKERS = 16
IO_HEADROOM = 2
DEFAULT_CORES = 4
def default_worker_count():
    detected = os.cpu_count() or DEFAULT_CORES
    return max(MIN_WORKERS, min(MAX_WORKERS, detected + IO_HEADROOM))

def safe_relative_path(virtual_path):
    parts = []
    for piece in virtual_path.replace("\\", "/").split("/"):
        if not piece or piece == ".":
            continue
        if piece == "..":
            continue
        cleaned = "".join(ch for ch in piece if ch not in '<>:"|?*')
        cleaned = cleaned.rstrip(" .")
        if cleaned:
            parts.append(cleaned)
    if not parts:
        return None
    return Path(*parts)

def extract_chunk(job):
    archive_path, output_root, entries = job

    written = 0
    written_bytes = 0
    failures = []

    output_root = Path(output_root)

    try:
        handle = open(archive_path, "rb", buffering=0)
    except OSError as exc:
        return (0, 0, [(archive_path, str(exc))])

    try:
        for virtual_path, offset, stored_size, real_size in entries:
            relative = safe_relative_path(virtual_path)
            if relative is None:
                failures.append((virtual_path, "unusable path"))
                continue

            destination = output_root / relative

            try:
                handle.seek(offset)
                blob = handle.read(stored_size)
                if len(blob) != stored_size:
                    failures.append((virtual_path, "short read"))
                    continue

                if stored_size != real_size:
                    data = zlib.decompress(blob, MAX_WBITS, real_size)
                    if len(data) != real_size:
                        failures.append(
                            (virtual_path, f"size mismatch {len(data)} != {real_size}")
                        )
                        continue
                else:
                    data = blob

                with open(destination, "wb") as out:
                    out.write(data)

                written += 1
                written_bytes += len(data)
            except zlib.error as exc:
                failures.append((virtual_path, f"zlib: {exc}"))
            except OSError as exc:
                failures.append((virtual_path, f"io: {exc}"))
    finally:
        handle.close()

    return (written, written_bytes, failures)

def build_jobs(game_dir, output_root, selected=None):
    jobs = []
    summary = []
    seen = set()

    for index, path in packidx.discover_archives(game_dir):
        if selected and path.name not in selected:
            continue

        archive = packidx.load_archive(path, index)

        entries = []
        archive_bytes = 0
        for item in archive.files:
            if item.path in seen:
                continue
            seen.add(item.path)
            entries.append((item.path, item.offset, item.stored_size, item.real_size))
            archive_bytes += item.real_size

        entries.sort(key=lambda row: row[1])
        summary.append((path.name, len(entries), archive_bytes))

        for start in range(0, len(entries), CHUNK_SIZE):
            jobs.append(
                (str(path), str(output_root), entries[start:start + CHUNK_SIZE])
            )

    return jobs, summary

def create_directories(output_root, jobs):
    wanted = set()
    for _, _, chunk in jobs:
        for virtual_path, _, _, _ in chunk:
            relative = safe_relative_path(virtual_path)
            if relative is not None:
                wanted.add(relative.parent)

    for relative in sorted(wanted):
        (Path(output_root) / relative).mkdir(parents=True, exist_ok=True)

    return len(wanted)

def run_unpack(game_dir, update_queue, cancel_event, worker_count=None, selected=None):
    game_root = packidx.resolve_game_root(game_dir)
    output_root = game_root
    worker_count = worker_count or default_worker_count()

    try:
        output_root.mkdir(parents=True, exist_ok=True)
        jobs, summary = build_jobs(game_root, output_root, selected)
        create_directories(output_root, jobs)
    except Exception as exc:
        update_queue.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        update_queue.put({"type": "finished"})
        return

    if not jobs:
        update_queue.put(
            {"type": "error", "message": "No SAO containers found in that folder."}
        )
        update_queue.put({"type": "finished"})
        return

    total_files = sum(count for _, count, _ in summary)
    total_bytes = sum(size for _, _, size in summary)

    done_files = 0
    done_bytes = 0
    error_count = 0
    started = time.time()

    update_queue.put(
        {
            "type": "state",
            "status": "Unpacking",
            "progress": 0.0,
            "total_files": total_files,
            "done_files": 0,
            "error_count": 0,
            "running": True,
            "output_root": str(output_root),
        }
    )

    cancelled = False

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        try:
            for written, written_bytes, failures in executor.map(extract_chunk, jobs):
                done_files += written
                done_bytes += written_bytes

                for virtual_path, reason in failures:
                    error_count += 1
                    if error_count <= 40:
                        update_queue.put(
                            {"type": "log", "message": f"Fail {virtual_path}: {reason}"}
                        )

                elapsed = max(0.001, time.time() - started)
                update_queue.put(
                    {
                        "type": "state",
                        "status": (
                            f"Unpacking {done_files}/{total_files}  "
                            f"{done_bytes / 2 ** 30:.2f} GB  "
                            f"{done_bytes / 2 ** 20 / elapsed:.0f} MB/s"
                        ),
                        "progress": done_files / total_files if total_files else 0.0,
                        "total_files": total_files,
                        "done_files": done_files,
                        "error_count": error_count,
                        "running": True,
                    }
                )

                if cancel_event.is_set():
                    cancelled = True
                    break
        except Exception as exc:
            update_queue.put(
                {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
            )

    elapsed = time.time() - started

    if cancelled:
        final = f"Cancelled after {done_files}/{total_files} files."
    elif error_count:
        final = (
            f"Done with {error_count} error(s). {done_files}/{total_files} files "
            f"in {elapsed:.0f}s."
        )
    else:
        final = (
            f"Unpacked {done_files} files, {done_bytes / 2 ** 30:.2f} GB in "
            f"{elapsed:.0f}s."
        )

    update_queue.put(
        {
            "type": "state",
            "status": final,
            "progress": 1.0 if not cancelled else done_files / max(1, total_files),
            "total_files": total_files,
            "done_files": done_files,
            "error_count": error_count,
            "running": False,
            "output_root": str(output_root),
        }
    )
    update_queue.put({"type": "finished"})
