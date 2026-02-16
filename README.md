# Synology-style thumbnail generator

Generates **@eaDir** thumbnails for photos and videos (SYNOPHOTO_THUMB_SM, M, XL only). When a thumbnail is created successfully, any matching `.fail` file is removed so that absence of `.fail` means the thumbnail is ready.

### Synology NAS

- **Install the community version of ffmpeg7** on your Synology (e.g. from Package Center or SynoCommunity). The DSM-built-in ffmpeg has ffprobe and many decoders (e.g. H.264) disabled, so video thumbnails will fail without ffmpeg7.
- **Run the script on the Synology** (e.g. via SSH). The generated `@eaDir` folders must live next to your media on the NAS so Synology Photos (and DSM) can read and use the thumbnails.

### Synology Package (SPK)

A package structure is included in the `package/` directory for creating a Synology SPK package. This allows installation via Package Center.

**To build the package:**
```bash
cd package
make package
```

This creates `syno-thumbs-1.0.0-noarch.spk` which can be installed via Package Center or manually with:
```bash
sudo synopkg install syno-thumbs-1.0.0-noarch.spk
```

After installation, scripts are available as:
- `/usr/local/bin/syno-thumbs`
- `/usr/local/bin/run-all-thumbs`
- `/usr/local/bin/syno-thumbs-daemon` (for scheduled runs)

### Configuration

The package includes a **configuration wizard** during installation where you can:
- Enable/disable automatic thumbnail generation
- Configure folders to process
- Set a schedule (cron format)
- Configure video thumbnail settings

After installation, edit `/var/packages/syno-thumbs/etc/syno_thumbs.conf` to change settings.

**Automatic scheduling:** If enabled, thumbnails are generated automatically on the configured schedule using cron.

See `package/CONFIG_GUIDE.md` for detailed configuration options.

See `package/README.md` for details on package structure and SynoCommunity submission.

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
| `--debug` | Print each created or existing thumbnail file |

### Running on a whole photo tree: `run_all_thumbs.sh`

To generate thumbnails in **every directory** under a photo root (e.g. `PhotoLibrary/2020/01/01`, `2021/01/02`, …), use the shell script. It runs `syno_thumbs.py` in each directory and does not descend into `@eaDir` folders.

```bash
./run_all_thumbs.sh /path/to/PhotoLibrary
```

Example (Synology):

```bash
./run_all_thumbs.sh /volume1/homes/user/Photos/PhotoLibrary
```

Keep `run_all_thumbs.sh` in the same directory as `syno_thumbs.py`.

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
