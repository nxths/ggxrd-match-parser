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
The image analysis is comically simple so there's a number of limitations:
* Videos must be raw gameplay footage, any picture-in-picture which shifts/resizes the game screen will break the image analysis. Netplay footage is also problematic because the connection bars display obscures the character name in the top left. Stream overlays should be ok if they don't obscure the top or center of the screen.
* Live streaming videos are unsupported.
* Youtube seems to continue processing videos after their initial upload, if the processed match timestamps appear both consistently and incorrectly offset this is probably why.  The ``ggxrd-rss-match-parser.py`` script will ignore videos uploaded within 36hrs for this reason.

# Notes
* An ``ERROR: requested format not available`` message is typically caused by trying to download a live streaming video. These can show up in youtube RSS feeds as the most recent video, should be ok to ignore when running ``ggxrd-rss-match-parser.py`` since older videos are processed first and there won't be any newer videos.
* If the scripts appear to be hung after downloading a youtube video, it's likely waiting on moviepy to finish its initial processing. Check to see if ffmpeg is consuming a lot of CPU - this indicates it's doing work. It can take a long time for lengthy videos, may need to let it run for a while.

# Further work (none of these are planned, but would be nice)
* OCR out the player names on the VS splash screen (would need to download videos in higher quality format)
* Detect when matches actually begin (skip over VS splash screen and character intros), and adjust the timestamp forwards accordingly
* Make the image analysis not terrible and train machine learning model to recognize character names/splashes properly
