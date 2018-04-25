#!/usr/bin/env python
import os
import re
import subprocess
import sys
import urllib.request


# *** Change below values before running ***
MAX_VIDEOS = 15                                   # max number of videos to keep parsed matches
RSS_URL = ''                                      # youtube RSS url, e.g. https://www.youtube.com/feeds/videos.xml?channel_id=UCDmFkuRZSbxyvqdK-cjMSog
MATCH_PARSER_FILEPATH = './ggxrd-match-parser.py' # change this to absolute path
TMP_VID_FILEPATH = './.youtube-vid'               # path for the temporarily downloaded youtube videos
TMP_MATCHES_OUTPUT_FILEPATH = './.temp-matches'   # path for temporary matches html
MATCHES_OUTPUT_FILEPATH = './matches.html'        # path for output matches html
SEEN_LINKS_FILEPATH = './.seen-links'             # path for file to keep track of previously parsed videos


PUBLISHED_RE = re.compile('<published>(?P<published>.+)</published>')
LINK_RE = re.compile('<link .+?href="(?P<href>.+?)"')
MATCHES_SEP = '<br><hr><br>'


def print_exit(s):
    print(s)
    sys.exit(1)

def item_published(item):
    m = PUBLISHED_RE.search(item)
    return m.group('published') if m else ''

def item_link(item):
    m = LINK_RE.search(item)
    return m.group('href') if m else ''

if __name__ == '__main__':
    if not RSS_URL:
        print_exit('Need to edit RSS_URL value, see comment towards top of this source file')

    try:
        rss = urllib.request.urlopen(RSS_URL).read().decode('utf-8')
    except Exception as e:
        print_exit(e)

    items = []
    item_start = rss.find('<entry>')
    item_end = -1

    while item_start != -1 and len(items) < MAX_VIDEOS:
        item_end = rss.find('</entry>', item_start)
        item = rss[item_start:(item_end + len('</entry>'))]
        items.append(item)
        item_start = rss.find('<entry>', item_end)

    try:
        with open(SEEN_LINKS_FILEPATH, 'r') as f:
            seen_links = set(f.read().splitlines())
    except Exception:
        seen_links = set()

    for item in reversed(items):
        published = item_published(item)
        link = item_link(item)

        if not published or not link or link in seen_links:
            continue

        subprocess.check_call(
            '"{}" -t "{}" -o "{}" "{}"'.format(
                MATCH_PARSER_FILEPATH,
                TMP_VID_FILEPATH,
                TMP_MATCHES_OUTPUT_FILEPATH,
                link,
            ),
            shell=True,
        )

        try:
            with open(TMP_MATCHES_OUTPUT_FILEPATH, 'r') as f:
                new_matches = f.read()
            os.remove(TMP_MATCHES_OUTPUT_FILEPATH)
        except Exception as e:
            print_exit(e)

        try:
            with open(MATCHES_OUTPUT_FILEPATH, 'r') as f:
                existing_matches = f.read().split(MATCHES_SEP)[:-1]
        except Exception:
            existing_matches = []

        with open(MATCHES_OUTPUT_FILEPATH, 'w') as f:
            f.write('<h2>{}</h2>\n'.format(published))
            f.write(new_matches)

            for matches in existing_matches[:MAX_VIDEOS - 1]:
                f.write(
                    '{}{}'.format(
                        matches,
                        MATCHES_SEP,
                    ),
                )

        with open(SEEN_LINKS_FILEPATH, 'a+') as f:
            f.write('{}\n'.format(link))
