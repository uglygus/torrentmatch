import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
import shutil
from pathlib import Path

import pytest

# === Import from your real module ===
# Adjust this import to wherever your functions are defined
from torrentmatch.tm import copy_files, name_similarity, quick_copy


def make_file(path: Path, size: int, content_byte=b"x"):
    """Create a fake file with a specific size."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(content_byte * size)
    return path


def fake_torrent_info(file_relpath, size):
    """Return a fake .torrent-style info dictionary."""
    return {"files": [{"path": file_relpath.parts, "length": size}]}


@pytest.fixture
def fake_environment(tmp_path):
    """Set up fake torrent + media directories."""
    torrents_dir = tmp_path / "torrents"
    media_in = tmp_path / "media_in"
    torrents_out = tmp_path / "out_torrents"
    media_out = tmp_path / "out_media"

    # Make directories
    for p in (torrents_dir, media_in, torrents_out, media_out):
        p.mkdir(parents=True, exist_ok=True)

    # Simulate one torrent with multiple files
    t1_name = "Prepared Playstation 2"
    torrent_file = torrents_dir / f"{t1_name}.torrent"
    torrent_info = fake_torrent_info(Path("VIDEO_TS") / "VTS_01_0.BUP", 100)
    make_file(torrent_file, 256)  # fake torrent file itself

    # Simulate local media folder
    make_file(media_in / t1_name / "VIDEO_TS" / "VTS_01_0.BUP", 100)
    make_file(media_in / t1_name / "VIDEO_TS" / "RANDOM_FILE.BUP", 100)
    make_file(media_in / t1_name / "VIDEO_TS" / "VTS_01_1.VOB", 300)

    # Return paths and info
    return {
        "torrents_dir": torrents_dir,
        "media_in": media_in,
        "torrents_out": torrents_out,
        "media_out": media_out,
        "torrent_info": torrent_info,
        "torrent_file": torrent_file,
    }


# === Tests ===


def test_copy_files_integration(fake_environment, monkeypatch):
    """Full end-to-end test that runs the matching and copying logic."""

    env = fake_environment

    # --- Prepare fake match results ---
    # The structure should match what your main script passes to copy_files
    results = [
        {
            "torrent": str(env["torrent_file"]),
            "torrent_obj": env["torrent_info"],
            "media": [env["media_in"] / "Prepared Playstation 2"],
        }
    ]

    copied = []

    # --- Patch shutil.copy2 to record copies without touching filesystem ---
    def fake_copy(src, dest):
        copied.append((src, dest))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest

    monkeypatch.setattr("yourmodule.shutil.copy2", fake_copy)

    # --- Run ---
    copy_files(results, env["torrents_out"], env["media_out"], env["media_in"])

    # --- Assertions ---
    # It should have picked the correct BUP file (best match)
    assert any("VTS_01_0.BUP" in str(src) for src, _ in copied)
    # It should not have picked RANDOM_FILE.BUP
    assert not any("RANDOM_FILE.BUP" in str(src) for src, _ in copied)
    # The destination structure should include the torrent name folder
    assert any("Prepared Playstation 2" in str(dest) for _, dest in copied)
    # Similarity should prefer matching names
    assert name_similarity("VTS_01_0.BUP", "VTS_01_0.BUP") >= 0.9
    assert name_similarity("VTS_01_0.BUP", "RANDOM_FILE.BUP") < 0.9

    print(f"Copied files ({len(copied)}):")
    for src, dest in copied:
        print(f"  {src} → {dest}")
