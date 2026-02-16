#!/usr/bin/env python3
"""
Generate Synology-style @eaDir thumbnails for photos and videos.
Uses ffmpeg. Creates only thumbnails (SM, M, XL). When a thumbnail is created,
any matching .fail file is removed so absence of .fail signals the thumb is ready.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Media extensions
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".gif", ".bmp", ".tiff", ".tif"}
VIDEO_EXTS = {".mov", ".mp4", ".avi", ".mkv", ".m4v", ".webm", ".wmv"}

# Thumbnail sizes (from your template)
# SM: longest edge 320  -> e.g. 320x240
# M:  shortest edge 320 -> e.g. 427x320
# XL: shortest edge 1280 (or full for video) -> e.g. 1707x1280
SIZE_SM_LONG = 320
SIZE_M_SHORT = 320
SIZE_XL_SHORT = 1280
# Video SM: longest edge (template had 427x240 for 1920x1080)
SIZE_VIDEO_SM_LONG = 427

# Synology package with full codec support (optional)
FFMPEG7_BIN = Path("/var/packages/ffmpeg7/target/bin/ffmpeg")
FFMPEG7_PROBE = Path("/var/packages/ffmpeg7/target/bin/ffprobe")


def resolve_ffmpeg_commands() -> tuple[list[str], list[str]]:
    """Use ffmpeg7 package on Synology if present, else PATH."""
    if FFMPEG7_BIN.is_file() and os.access(FFMPEG7_BIN, os.X_OK):
        ffprobe_cmd = (
            [str(FFMPEG7_PROBE)]
            if FFMPEG7_PROBE.is_file() and os.access(FFMPEG7_PROBE, os.X_OK)
            else ["ffprobe"]
        )
        return [str(FFMPEG7_BIN)], ffprobe_cmd
    return ["ffmpeg"], ["ffprobe"]


def get_media_info_ffprobe(path: Path, ffprobe_cmd: list[str], ffmpeg_cmd: list[str]) -> dict | None:
    """Get width, height via ffprobe (or ffmpeg -i fallback when ffprobe is disabled, e.g. on Synology NAS)."""
    # Fallback 2: ImageMagick identify (works for most images including HEIC if supported)
    try:
        out = subprocess.run(
            ["identify", "-format", "%w,%h", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0:
            line = (out.stdout or "").strip()
            if line and "," in line:
                w_str, h_str = line.split(",", 1)
                w, h = int(w_str), int(h_str)
                if w > 0 and h > 0:
                    return {"width": w, "height": h, "duration": None}
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    # Fallback 3: heif-info (for HEIC files)
    try:
        out = subprocess.run(
            ["heif-info", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0:
            for line in (out.stdout or "").splitlines():
                m = re.search(r"size:\s*(\d+)\s*x\s*(\d+)", line.lower())
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    if w > 0 and h > 0:
                        return {"width": w, "height": h, "duration": None}
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    # Try ffprobe first (not available on some NAS builds: --disable-ffprobe)
    try:
        out = subprocess.run(
            ffprobe_cmd
            + [
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0:
            line = (out.stdout or "").strip().splitlines()[0]
            if line:
                parts = line.split(",")
                w = int(parts[0]) if len(parts) > 0 and parts[0].strip().isdigit() else None
                h = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else None
                if w and h:
                    return {"width": w, "height": h, "duration": None}
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    # Fallback: parse "Stream #0:0: Video: ... 1920x1080 ..." from ffmpeg -i stderr
    try:
        out = subprocess.run(
            ffmpeg_cmd + ["-i", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        err = (out.stderr or "") + (out.stdout or "")
        for line in err.splitlines():
            if "Video:" in line or "video:" in line:
                m = re.search(r"(\d{2,})\s*x\s*(\d{2,})", line)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    if w > 0 and h > 0:
                        return {"width": w, "height": h, "duration": None}
                break
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None



def scale_args(width: int, height: int, size_spec: str) -> tuple[int, int]:
    """Return (w, h) for scale filter. size_spec: 'sm' | 'm' | 'xl'."""
    if size_spec == "sm":
        # Longest edge = SIZE_SM_LONG
        if width >= height:
            if width <= SIZE_SM_LONG:
                return width, height
            return SIZE_SM_LONG, max(1, round(height * SIZE_SM_LONG / width))
        else:
            if height <= SIZE_SM_LONG:
                return width, height
            return max(1, round(width * SIZE_SM_LONG / height)), SIZE_SM_LONG
    elif size_spec == "m":
        # Shortest edge = SIZE_M_SHORT
        if width >= height:
            if height <= SIZE_M_SHORT:
                return width, height
            return max(1, round(width * SIZE_M_SHORT / height)), SIZE_M_SHORT
        else:
            if width <= SIZE_M_SHORT:
                return width, height
            return SIZE_M_SHORT, max(1, round(height * SIZE_M_SHORT / width))
    else:  # xl
        # Shortest edge = SIZE_XL_SHORT (cap to original)
        if width >= height:
            if height <= SIZE_XL_SHORT:
                return width, height
            return max(1, round(width * SIZE_XL_SHORT / height)), SIZE_XL_SHORT
        else:
            if width <= SIZE_XL_SHORT:
                return width, height
            return SIZE_XL_SHORT, max(1, round(height * SIZE_XL_SHORT / width))


def scale_args_video(width: int, height: int, size_spec: str) -> tuple[int, int]:
    """Video: SM = longest 427; M = 640 long; XL = original (or 1280 short)."""
    if size_spec == "sm":
        if width >= height:
            if width <= SIZE_VIDEO_SM_LONG:
                return width, height
            return SIZE_VIDEO_SM_LONG, max(1, round(height * SIZE_VIDEO_SM_LONG / width))
        else:
            if height <= SIZE_VIDEO_SM_LONG:
                return width, height
            return max(1, round(width * SIZE_VIDEO_SM_LONG / height)), SIZE_VIDEO_SM_LONG
    elif size_spec == "m":
        long_edge = 640
        if width >= height:
            if width <= long_edge:
                return width, height
            return long_edge, max(1, round(height * long_edge / width))
        else:
            if height <= long_edge:
                return width, height
            return max(1, round(width * long_edge / height)), long_edge
    else:
        return width, height

def run_ffmpeg_thumb(
    input_path: Path,
    output_path: Path,
    width: int,
    height: int,
    is_video: bool,
    ffmpeg_cmd: list[str],
    seek: float = 0.0,
) -> bool:
    """Generate one thumbnail with ffmpeg. Returns True on success."""
    scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
    cmd = ffmpeg_cmd + [
        "-y",
        "-v", "error",
        "-hide_banner", "-loglevel", "error",
    ]
    if is_video:
        cmd += ["-ss", str(seek), "-i", str(input_path), "-vframes", "1"]
        cmd += ["-vf", scale, "-q:v", "3", str(output_path)]
    else:
        print("using convert size: " + str(width))
        cmd = ["convert"]
        cmd += ["-auto-orient", "-thumbnail", str(width), input_path, output_path]
        
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and output_path.is_file()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def process_file(
    media_path: Path,
    ea_dir: Path,
    video_seek: float,
    dry_run: bool,
    debug: bool,
    force: bool,
    ffmpeg_cmd: list[str],
    ffprobe_cmd: list[str],
) -> bool:
    """Process one photo or video: create @eaDir/Basename.ext/ and thumbnails only."""
    name = media_path.name
    ext = media_path.suffix.lower()
    is_video = ext in VIDEO_EXTS
    is_photo = ext in PHOTO_EXTS
    if not is_photo and not is_video:
        return True

    ea_subdir = ea_dir / name
    if dry_run:
        print(f"[dry-run] Would process: {media_path} -> {ea_subdir}")
        return True

    ea_subdir.mkdir(parents=True, exist_ok=True)

    # Skip entirely if all three thumbnails already exist
    if not force and all((ea_subdir / f"SYNOPHOTO_THUMB_{s}.jpg").is_file() for s in ("SM", "M", "XL")):
        if debug:
            print(f"    (all thumbs exist, skipped)")
        return True

    info = get_media_info_ffprobe(media_path, ffprobe_cmd, ffmpeg_cmd)
    print(info)
    if not info:
        print(f"Warning: could not get dimensions for {media_path}", file=sys.stderr)
        return False

    w, h = info["width"], info["height"]
    if w <= 0 or h <= 0:
        print(f"Warning: invalid size for {media_path}", file=sys.stderr)
        return False

    def do_thumb(suffix: str, size_spec: str) -> bool:
        print(size_spec)
        if is_video:
            tw, th = scale_args_video(w, h, size_spec)
        else:
            tw, th = scale_args(w, h, size_spec)
        print(str(th) + " " + str(tw))
        out = ea_subdir / f"SYNOPHOTO_THUMB_{suffix}.jpg"
        fail_path = ea_subdir / f"SYNOPHOTO_THUMB_{suffix}.fail"
        
        if not force and out.is_file():
            fail_path.unlink(missing_ok=True)
            if debug:
                print(f"    exists: {name}/{out.name}")
            return True
        ok = run_ffmpeg_thumb(media_path, out, tw, th, is_video, ffmpeg_cmd, seek=video_seek)
        if ok:
            fail_path.unlink(missing_ok=True)  # no .fail = thumbnail ready
            if debug:
                print(f"    created: {name}/{out.name}")
        else:
            fail_path.touch()
            if debug:
                print(f"    created: {name}/{fail_path.name} (thumbnail failed)")
        return ok

    do_thumb("SM", "sm")
    do_thumb("M", "m")
    do_thumb("XL", "xl")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Synology-style @eaDir thumbnails for photos and videos."
    )
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="Directory containing media files (default: current directory)",
    )
    parser.add_argument(
        "--ea-dir",
        type=Path,
        default=None,
        help="Override @eaDir location (default: <directory>/@eaDir)",
    )
    parser.add_argument(
        "--video-seek",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="Seek position in seconds for video thumbnails (default: 0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be done",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print each created thumbnail or .fail file",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force thumbnail generation even if all three thumbnails already exist",
    )
    args = parser.parse_args()

    directory = args.directory.resolve()
    if not directory.is_dir():
        print(f"Error: not a directory: {directory}", file=sys.stderr)
        return 1

    ea_dir = (args.ea_dir or (directory / "@eaDir")).resolve()

    ffmpeg_cmd, ffprobe_cmd = resolve_ffmpeg_commands()
    try:
        subprocess.run(ffmpeg_cmd + ["-version"], capture_output=True, check=True, timeout=5)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("Error: ffmpeg is required (tried: {}).".format(ffmpeg_cmd[0]), file=sys.stderr)
        return 1

    if args.debug and not args.dry_run and "ffmpeg7" in ffmpeg_cmd[0]:
        print(f"Using: {ffmpeg_cmd[0]}\n")

    exts = PHOTO_EXTS | VIDEO_EXTS
    count = 0
    for f in sorted(directory.iterdir(), key=lambda p: p.name):
        if f.is_file() and f.suffix.lower() in exts:
            if args.debug and not args.dry_run:
                print(f"{f.name}:")
            process_file(
                f, ea_dir,
                video_seek=args.video_seek,
                dry_run=args.dry_run,
                debug=args.debug,
                force=args.force,
                ffmpeg_cmd=ffmpeg_cmd,
                ffprobe_cmd=ffprobe_cmd,
            )
            count += 1

    if not args.dry_run:
        print(f"Processed {count} file(s). Thumbnails in {ea_dir}")
    else:
        print(f"Would process {count} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
