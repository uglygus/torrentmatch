import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from torrentool.api import Torrent


def normalize_path(path: Path) -> Path:
    parts = [unicodedata.normalize("NFC", part) for part in path.parts]
    return Path(*parts)


def get_torrent_files(torrent_dir: Path) -> list[tuple[Path, Torrent]]:
    return [(f, Torrent.from_file(f)) for f in torrent_dir.glob("*.torrent*")]


def get_files_from_torrent(torrent: Torrent) -> set[Path]:
    return {normalize_path(Path(file_path)) for file_path, _ in torrent.files}


def get_media_files(media_dir: Path) -> set[Path]:
    ignored = {".DS_Store", "Thumbs.db", "desktop.ini", "ehthumbs.db", "._.DS_Store"}
    return {
        normalize_path(file.relative_to(media_dir))
        for file in media_dir.rglob("*")
        if file.is_file() and file.name not in ignored
    }


def compare_torrents_with_media(torrent_dir: Path, media_dir: Path):
    torrents = get_torrent_files(torrent_dir)
    media_files = get_media_files(media_dir)

    all_torrent_files = set()
    missing_by_torrent = defaultdict(list)

    for torrent_path, torrent in torrents:
        files = get_files_from_torrent(torrent)
        all_torrent_files.update(files)
        for f in files:
            if f not in media_files:
                missing_by_torrent[torrent_path.name].append(f)

    # Report extra media files
    extra_media_files = media_files - all_torrent_files
    if extra_media_files:
        print("📁 Files in media directory not in any torrent:")
        for f in sorted(extra_media_files):
            print(f"  {f}")
    else:
        print("✅ All media files are referenced in torrents.")

    print()

    # Report missing files per torrent
    if missing_by_torrent:
        print("⚠️  Files referenced by torrents but missing from media directory:")
        for torrent_name, files in sorted(missing_by_torrent.items()):
            print(f"  {torrent_name}")
            for f in sorted(files):
                print(f"    {f}")
    else:
        print("✅ All torrent files are accounted for in media.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 torrentmatch.py /path/to/torrents /path/to/media")
        sys.exit(1)

    torrent_path = Path(sys.argv[1])
    media_path = Path(sys.argv[2])

    if not torrent_path.is_dir() or not media_path.is_dir():
        print("Error: both arguments must be directories.")
        sys.exit(1)

    compare_torrents_with_media(torrent_path, media_path)
