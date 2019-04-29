![Example output html screenshot](https://raw.githubusercontent.com/nxths/ggxrd-match-parser/9532188857f36eec9dd56241e2b4285efe6561a6/screenshots/example.jpg)

# Overview
This project is for parsing out matches from youtube videos for Guilty Gear Xrd. Specifically, this script will generate an html file containing match start times with character names. See example screenshot above, each match is a timestamped youtube video link. 1 player modes (e.g. training) will be detected and ignored.

* ``ggxrd-match-parser.py``: Script for downloading and parsing youtube videos, run with ``--help`` for more details.

The source should be cross platform but has only been tested on linux and windows.

# Dependencies
* [python 3.x](https://www.python.org/)
* [moviepy](https://zulko.github.io/moviepy/)
  * [ffmpeg](https://www.ffmpeg.org/)
* [pillow](https://pillow.readthedocs.io/)
* [imagehash](https://github.com/JohannesBuchner/imagehash)
* [youtube-dl](https://rg3.github.io/youtube-dl/) (needs to be in PATH)

# Limitations
* Videos must be direct gameplay footage, if the game screen is shifted it will break the image analysis. Stream overlays should be ok if they don't obscure the center of the screen.
* Live streaming videos are unsupported.

# Notes
* An ``ERROR: requested format not available`` message is typically caused by trying to download a live streaming video.
* If parsed match timestamps appear incorrectly and consistently offset, this may be because the video is too recent. Youtube appears to continue processing videos after their initial upload, which can result in an erroneous partial video download. This can be an issue for up to ~48hrs for long videos (10hrs+), depends on the video length.

# Further work
* OCRing out the player names on the VS splash screen (need to download videos in higher quality format) would be nice. Some work has been done here in a [fork](https://github.com/keeponrockin-db/ggxrd-match-parser).
