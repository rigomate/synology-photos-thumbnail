# Synology-style thumbnail generator

Generates **@eaDir** thumbnails for photos and videos (SYNOPHOTO_THUMB_SM, M, XL only). When a thumbnail is created successfully, any matching `.fail` file is removed so that absence of `.fail` means the thumbnail is ready.

## Requirements

- **Python 3.8+** (stdlib only)
- **ffmpeg** on your PATH (used for thumbnails and probe)

Install ffmpeg if needed:

```bash
# Debian/Ubuntu
sudo apt install ffmpeg
```

## Usage

From the folder that contains your media (and where you want `@eaDir`):

```bash
python3 syno_thumbs.py
```

Or specify a directory:

```bash
python3 syno_thumbs.py /path/to/photos
```

Options:

| Option | Description |
|--------|-------------|
| `--ea-dir PATH` | Put @eaDir elsewhere (default: `<directory>/@eaDir`) |
| `--video-seek SECONDS` | Time in seconds for video thumbnail frame (default: 0) |
| `--dry-run` | Print what would be done without writing files |

## Output layout (template from your folder)

For each media file (e.g. `IMG_5966.JPG`, `IMG_5968.MOV`), the script creates:

- `@eaDir/IMG_5966.JPG/`
  - `SYNOPHOTO_THUMB_SM.jpg` – small (longest edge 320)
  - `SYNOPHOTO_THUMB_M.jpg` – medium (short edge 320)
  - `SYNOPHOTO_THUMB_XL.jpg` – large (short edge 1280)
  - `SYNOPHOTO_THUMB_*.fail` only when that size fails (removed when the thumb is created)

Thumbnail sizes are derived from your existing Synology-generated files (e.g. 320×240 SM, 427×320 M, 1707×1280 XL for a 4032×3024 photo).

## Notes

- Only thumbnails are created; no SYNOINDEX_MEDIA_INFO or @SynoEAStream files.
- If a thumbnail is created successfully, the matching `.fail` file (if any) is removed so that “no .fail” means the thumbnail is ready.
- Supported photo extensions: jpg, jpeg, png, heic, gif, bmp, tiff, tif.
- Supported video extensions: mov, mp4, avi, mkv, m4v, webm, wmv.
