![Example output html screenshot](https://raw.githubusercontent.com/nxths/ggxrd-match-parser/master/screenshots/example.jpg)

# Overview
This project is for parsing out matches from youtube videos for Guilty Gear Xrd. Specifically, these scripts will generate an html file containing match start times with character names. See example screenshot above, each match is a timestamped youtube video link. Training/demo/MOM mode matches will attempt to be detected and ignored.

* ``ggxrd-match-parser.py``: Main script for downloading and parsing youtube videos, run with ``--help`` for more details.
* ``ggxrd-rss-match-parser.py``: Utility script to run the match parser over a series of videos from a youtube RSS feed. See comment towards top of source file, should edit variables for the RSS url and files before running.

The scripts should be cross platform but have only been tested on linux and windows.

# Dependencies
* [python 3.x](https://www.python.org/)
* [moviepy](https://zulko.github.io/moviepy/) (may need to upgrade pip itself first if installing through pip)
  * [ffmpeg](https://www.ffmpeg.org/)
* [pillow](https://pillow.readthedocs.io/)
* [youtube-dl](https://rg3.github.io/youtube-dl/) (needs to be in PATH)

# Limitations
The image analysis is very simple so there's a number of limitations:
* Videos must be raw gameplay footage, any picture-in-picture which shifts/resizes the game screen will break the image analysis. Stream overlays should be ok if they don't obscure the center of the screen.
* Live streaming videos are unsupported.
* Youtube seems to continue processing videos after their initial upload, if the processed match timestamps appear both consistently and incorrectly offset this is probably why.  The ``ggxrd-rss-match-parser.py`` script will ignore videos uploaded within 48hrs for this reason.

# Notes
* An ``ERROR: requested format not available`` message is typically caused by trying to download a live streaming video.

# Further work (none of these are planned, but would be nice)
* OCR out the player names on the VS splash screen (would need to download videos in higher quality format)
* Detect when matches actually begin (skip over VS splash screen and character intros), and adjust the timestamp forwards accordingly
