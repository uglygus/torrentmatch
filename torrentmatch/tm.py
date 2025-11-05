#!/usr/bin/env python3

import argparse
import difflib
import shutil
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from torrentool.api import Torrent
from torrentool.torrent import Torrent

ignored = {".DS_Store", "Thumbs.db", "@eaDir", "desktop.ini", "ehthumbs.db", "._.DS_Store"}
ignored_suffixes = {"@SynoEAStream", "@SynoResource"}


def is_ignored(filename):

    if filename in ignored:
        return True
    for suffix in ignored_suffixes:
        if filename.endswith(suffix):
            return True
    return False


def normalize_path(path: Path) -> Path:
    parts = [unicodedata.normalize("NFC", part) for part in path.parts]
    return Path(*parts)


def get_torrent_files(torrent_dir: Path) -> list[tuple[Path, Torrent]]:
    return [(f, Torrent.from_file(f)) for f in torrent_dir.glob("*.torrent*")]


def files_in_torrent(torrent: Torrent) -> set[Path]:
    return {normalize_path(Path(file_path)) for file_path, _ in torrent.files}


def get_media_files(media_dir: Path) -> set[Path]:
    return {
        normalize_path(file.relative_to(media_dir))
        for file in media_dir.rglob("*")
        if file.is_file()
    }


def print_results(results):
    """Pretty-print comparison results."""
    for item in results:
        torrent_name = item["torrent"]
        matches = item["media"]

        if not matches:
            print(f"{torrent_name} | No match found")
        else:
            print(f"{torrent_name} | Matches:")
            for f in matches:
                print(f"    -> {f}")
        print()


def quick_copy(src, dest,overwrite=True):
    """Copy file only if destination does not exist or differs in size.
    By default (overwrite=True), existing files with different sizes will be overwritten.
    If overwrite=False, existing files with different sizes will not be overwritten new file will be renamed.
    
    Creates parent directories as needed.
    
    """

    #print('quick_copy() src=', src, ' dest=', dest, ' overwrite=', overwrite)
    try:
        if src.resolve() == dest.resolve():
            return

        if overwrite and dest.exists() and dest.stat().st_size == src.stat().st_size:
            pass #print("quick_copy() skipping copy; destination exists with same size.")
            return
        if not overwrite and dest.exists() and dest.stat().st_size != src.stat().st_size:
            dest = dest.with_name(
                f"{dest.name.removesuffix('.torrent').removesuffix('.added')}_{src.stat().st_size}.torrent"
            )

            print("renaming source file as dest exists with different size src.name")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    except Exception as e:
        print(f"quick_copy failed for {src} → {dest}: {e}")


def name_similarity(a, b):
    """Return a similarity ratio (0–1) between two filenames (ignoring case and extensions)."""
    a = Path(a).stem.lower().replace("_", " ")
    b = Path(b).stem.lower().replace("_", " ")
    return SequenceMatcher(None, a, b).ratio()


def report_torrent_media_mismatches(torrent_dir: Path, media_dir: Path):
    torrents = get_torrent_files(torrent_dir)
    media_files = get_media_files(media_dir)

    #print('torrents=', torrents, '\n')
    #print('media_files=', media_files, '\n')

    all_torrent_files = set()
    missing_by_torrent = defaultdict(list)

    for torrent_path, torrent in torrents:
        files = files_in_torrent(torrent)
        all_torrent_files.update(files)
        for f in files:
            if f not in media_files and not is_ignored(f.name):
                missing_by_torrent[torrent_path.name].append(f)

    extra_media_files = media_files - all_torrent_files
    if extra_media_files:
        print("Files in media directory not in any torrent:")
        #print('extra_media_files=', extra_media_files, '\n ')
        for f in sorted(extra_media_files):
            if not is_ignored(f.name):
                print(f"  {f}")
    else:
        print("All media files are referenced in torrents.")
    print()

    if missing_by_torrent:
        print("Files referenced by torrents but missing from media directory:")
        for torrent_name, files in sorted(missing_by_torrent.items()):
            print(f"  {torrent_name}")
            for f in sorted(files):
                if not is_ignored(f.name):
                    print(f"    {f}")
    else:
        print("All torrent files are accounted for in media.")


def compare_torrents_with_media(torrent_dir: Path, media_dir: Path, size_tolerance_bytes=0):
    """
    Compare torrent files to media directory by total size and file count.
    Returns a list of dicts:
        [{ "torrent": <torrent filename>, "media": [<matched media paths>] }]
    """
    torrents = get_torrent_files(torrent_dir)
    # print("torents=", torrents, "\n")
    print("Collecting torrents and their media.\n")

    results = []

    # Precompute media folder statistics
    folder_stats = {}
    for folder in [d for d in media_dir.rglob("*") if d.is_dir()]:
        total_size = 0
        file_count = 0
        for f in folder.rglob("*"):
            if f.is_file() and not is_ignored(f.name):
                try:
                    total_size += f.stat().st_size
                    file_count += 1
                except (OSError, FileNotFoundError):
                    continue
        if file_count > 0:
            folder_stats[folder] = (total_size, file_count)

    # print(f"folder_stats={folder_stats}\n")

    # Precompute media file sizes for single-file torrents
    media_files = [f for f in media_dir.rglob("*") if f.is_file()]
    media_by_size = defaultdict(list)

    for f in media_files:
        # print("media_files f==", f)
        try:
            if not is_ignored(f.name):
                media_by_size[f.stat().st_size].append(f)
        except (OSError, FileNotFoundError):
            continue

    # print(f"media_by_size={media_by_size}\n")

    # Main comparison loop
    for torrent_path, torrent in torrents:

        #print("top of main comparison for loop")

        torrent_name = torrent_path.name
        torrent_files = list(torrent.files)

        #print("torrent_name=", torrent_name)

        if not torrent_files:
            continue

        result_entry = {"torrent": torrent_name, "media": []}

        tsize = 0
        for size, files in media_by_size.items():
            tsize += size
           #{size}, files={files}, tsize={tsize}\n")

        total_torrent_files_size = sum(size for _, size in torrent_files)
        #print(f"torrent_name={torrent_name}, total_torrent_files_size={total_torrent_files_size}")
        #print(f"tsize (size of actual media files)={tsize}\n")

        if len(torrent_files) == 1:
            # Single-file torrent → compare against individual media files
            file_path, file_size = torrent_files[0]
            matches = [
                f
                for size, files in media_by_size.items()
                if abs(size - file_size) <= size_tolerance_bytes
                for f in files
            ]
            result_entry["media"].extend(matches)

        else:
            # Multi-file torrent → compare against media folders
            total_size = sum(size for _, size in torrent_files)
            file_count = len(torrent_files)
            # print(
            #     f"torrent_name={torrent_name}, total_size={total_size}, file_count={file_count}\n"
            # )
            matches = [
                folder
                for folder, (folder_size, folder_count) in folder_stats.items()
                if abs(folder_size - total_size) <= size_tolerance_bytes
                and folder_count == file_count
            ]
            result_entry["media"].extend(matches)

        #print("result_entry=", result_entry)
        results.append(result_entry)

    #print("returning results ==", results)

    return results


def collect_torrents_and_media(results, torrents_in, media_in, media_out, torrents_out):
    """
    Copy matched torrent and media files (or directories) to their respective output folders.
    - Creates directories as needed.
    - Renames media files to match the torrent info.
    - Picks best match by size first, then fuzzy filename if multiple candidates.
    """
    print('results=', results  )

    for item in results:
        torrent_name = item["torrent"]
        # print(f"\n\nProcessing torrent: {torrent_name}")
        # print(f"type torrent_name= {type(torrent_name)} ...")

        # print(f"item= {item} ")

        matches = item.get("media", [])

        if not matches:
            print(f" X  {torrent_name}")
            continue
        print('matches=', matches  )

        print(f"... {torrent_name} ...")

        torrent_path = Path(torrents_in) / torrent_name

        try:
            torrent_obj = Torrent.from_file(torrent_path)
        except Exception as e:
            print(f"Failed to load torrent {torrent_path}: {e}")
            continue

        # --- Copy torrent file ---
        dest_torrent_path = Path(torrents_out) / torrent_name
        # dest_torrent_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_torrent_path.suffix == ".added":
            dest_torrent_path = dest_torrent_path.with_suffix("")
        quick_copy(torrent_path, dest_torrent_path, overwrite = False)

        # --- Destination directory based on torrent name ---
        info = getattr(torrent_obj, "_struct", {}).get("info", {})
        torrent_root_name = info.get("name") or torrent_obj.name or "Unknown_Torrent"
        # print('torrent_root_name=', torrent_root_name)
        safe_name = torrent_root_name.replace("/", "_").strip()
        # print('safe_name=', safe_name)

        # --- Multi-file torrents ---
        torrent_files = info.get("files", [])
        if torrent_files:
            dest_dir = Path(media_out) / safe_name
            # print('dest_dir=', dest_dir)
            # dest_dir.mkdir(parents=True, exist_ok=True)
            # print(f" Found {len(torrent_files)} files in torrent metadata.")
            for tf in torrent_files:
                tf_length = tf.get("length")
                tf_path_parts = tf.get("path", [])
                tf_path = Path(*tf_path_parts)
                dest_file = dest_dir / tf_path

                # Collect all candidate files of matching size
                size_matches = []
                for media_path in matches:
                    size_matches.extend(
                        [
                            lf
                            for lf in Path(media_path).rglob("*")
                            if lf.is_file() and lf.stat().st_size == tf_length
                        ]
                    )

                if not size_matches:
                    print(f"No local file of size {tf_length} found for {tf_path}")
                    continue

                # Pick best match
                if len(size_matches) == 1:
                    candidate = size_matches[0]
                #   print(f" Unique size match found: {candidate}")

                # Try exact filename match first
                exact_name_matches = [
                    lf for lf in size_matches if lf.name.lower() == tf_path.name.lower()
                ]
                if exact_name_matches:
                    candidate = exact_name_matches[0]
                # print(f" Exact filename match found: {candidate}")
                else:
                    # fuzzy match
                    scores = [(lf, name_similarity(tf_path.name, lf.name)) for lf in size_matches]
                    scores.sort(key=lambda x: x[1], reverse=True)
                    best_file, best_score = scores[0]
                    candidate = best_file if best_score > 0.55 else size_matches[0]
                    print(
                        f" Multiple size matches found. Best name match: {candidate} (score={best_score:.2f})"
                    )

                # dest_file.parent.mkdir(parents=True, exist_ok=True)

                print(f"candidate.relative_to(media_in)       = {candidate.relative_to(media_in)}")
                print(f"dest_file.relative_to(dest_dir.parent) = {dest_file.relative_to(dest_dir.parent)}")

                if candidate.relative_to(media_in) == dest_file.relative_to(dest_dir.parent):
                    print(f"  >     Copy!: {candidate.relative_to(media_in)}")
                else:
                    print(f"  >     Copy & rename!: {candidate.relative_to(media_in)} → {dest_file.relative_to(dest_dir.parent)}")
                quick_copy(candidate, dest_file)
        else:
            # --- Single-file torrent ---
            print(f" Single-file torrent: copying directly")
            dest_dir = Path(media_out)
            print('dest_dir=', dest_dir)
            print("torrent_obj", torrent_obj)
            print("torrent_obj.name", torrent_obj.name)
            for media_path in matches:
                # print(f" Found media file: {media_path}")
                media_path = Path(media_path)
                dest_file = dest_dir / torrent_obj.name

                # print(f"  >     Copy: {media_path.relative_to(media_in)}")
                print(f"media_path.relative_to(media_in)      = {media_path.relative_to(media_in)}")
                print(f"dest_file.relative_to(dest_dir.parent) = {dest_file.relative_to(dest_dir)}")

                if media_path.relative_to(media_in) == dest_file.relative_to(dest_dir):
                    print(f"  >     Copy single: {media_path}")

                else:
                    print(f"  >     Copy & rename: {media_path} → {dest_file}")
                quick_copy(media_path, dest_file)
                # shutil.copy2(media_path, dest_file)


def parse_args():

    def existing_dir(path_str) -> Path:
        """Argparse type: ensure path exists and is a directory."""
        p = Path(path_str)
        if not p.exists():
            raise argparse.ArgumentTypeError(f"Path does not exist: {p}")
        if not p.is_dir():
            raise argparse.ArgumentTypeError(f"Path is not a directory: {p}")
        return p

    parser = argparse.ArgumentParser(
            prog="torrentmatch",
            description="Compare or collect torrent and media files."
        )

    # Mutually exclusive group for the two modes
    mode_group = parser.add_mutually_exclusive_group(required=True)

    mode_group.add_argument(
        "-c",
        "--collect",
        nargs=2,
        metavar=("TORRENT_dir", "MEDIA_dir"),
        type=existing_dir,
        help="Copy matched torrents and media to organized output folders.",
    )

    mode_group.add_argument(
        "-r",
        "--report",
        nargs=2,
        metavar=("TORRENT_dir", "MEDIA_dir"),
        type=existing_dir,
        help="Generate a detailed comparison between torrents and media files, "
        "listing missing or unreferenced files.",
    )

    # Output dirs (only required for --collect)
    parser.add_argument(
        "--torrents-out",
        metavar="DIR",
        help="Output directory for matched torrent files (required by --collect)."
    )

    parser.add_argument(
        "--media-out",
        metavar="DIR",
        help="Output directory for matched media files (required by --collect)."
    )

    args = parser.parse_args()

    # --- enforce required arguments for --collect ---
    if args.collect:
        if not args.torrents_out or not args.media_out:
            parser.error("--collect requires both --torrents-out and --media-out.")

    return args


if __name__ == "__main__":
    args = parse_args()

    if args.collect:
        torrent_dir, media_dir = map(Path, args.collect)
        print(f"[COLLECTING Torrents and matching media]\n Torrents: {torrent_dir}\n Media: {media_dir}")
        print(f" Output torrents: {args.torrents_out}\n Output media: {args.media_out}")

        results = compare_torrents_with_media(torrent_dir, media_dir)
        print('-----> Results:')
        print_results(results)
        print('--------')


        collect_torrents_and_media(
            results,
            torrent_dir,
            media_dir,
            args.media_out,
            args.torrents_out,
        )

        #Run a report to double check ouw work
        torrent_dir = args.torrents_out
        media_dir = args.media_out
        print(f"Running REPORT. Generate a detailed comparison between torrents and media files"
        f"listing missing or unreferenced files.\nTorrent directory: {torrent_dir}\nMedia directory: {media_dir}")
        report_torrent_media_mismatches(torrent_dir, media_dir)


    elif args.report:
        torrent_dir, media_dir = map(Path, args.report)
        print(f"Running REPORT. Generate a detailed comparison between torrents and media files"
        f"listing missing or unreferenced files.\nTorrent directory: {torrent_dir}\nMedia directory: {media_dir}")
        report_torrent_media_mismatches(torrent_dir, media_dir)
