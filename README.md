## torrentmatch.py

Compares a folder of torrents to a folder of media. Finds torrents that are missing media files and finds media files that do not belong to any torrents.

This is particularly useful for finding old or unneeded files in a torrent directory that aren't served by any loaded torrents anymore.

### Usage

```bash
python3 torrentmatch.py -h
usage: torrentmatch.py [-h] [-c] [--torrents-out TORRENTS_OUT] [--media-out MEDIA_OUT] torrents_in media_in

Commandline file processor python template

positional arguments:
  torrents_in           existing folder of torrent files
  media_in              existing folder of media files

options:
  -h, --help            show this help message and exit
  -c, --collect         collect media from renamed sources and move matches based on size and name similarity
  --torrents-out TORRENTS_OUT
                        folder to copy matched torrent files to. required for --collect
  --media-out MEDIA_OUT
                        folder to copy matched media files to. required for --collect
```
