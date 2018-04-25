#!/usr/bin/env python
import argparse
import datetime
import os
import re
import subprocess
import sys

from PIL import Image
from moviepy.video.io.VideoFileClip import VideoFileClip


# *** Change this to absolute path ***
MASKS_DIRPATH = './masks'


RGB_DIFF_THRESHOLD = 75
TIME_LIMIT_RGB_DIFF_THRESHOLD = 85
CHAR_RGB_DIFF_THRESHOLD = 125
SKIP_SECS = 10


class Mask(object):
    def __init__(self, filepath):
        self.filepath = filepath
        self.img_data = list(
            Image.open(
                '{}/{}'.format(MASKS_DIRPATH, filepath),
            ).getdata(),
        )

VS_MASK = Mask('vs.png')

PRESS_START_MASK = Mask('press-start-button.png')
INSERT_COIN_MASK = Mask('insert-coin.png')

TIME_LIMIT_MASKS = [
    Mask('time-limit-left.png'),
    Mask('time-limit-right.png'),
]

CHAR_MASKS = [
    Mask('chars/{}'.format(filepath))
    for filepath in os.listdir('{}/chars'.format(MASKS_DIRPATH))
]

def compare_rgb(mask, vid_rgb):
    total_rgb_diff = 0
    count = 0

    for i, (img_r, img_g, img_b, _) in enumerate(mask.img_data):
        if img_r == 255 and img_g == 255 and img_b == 255:
            continue

        vid_r = vid_rgb[i * 3]
        vid_g = vid_rgb[i * 3 + 1]
        vid_b = vid_rgb[i * 3 + 2]

        diff = abs(img_r - vid_r) + abs(img_g - vid_g) + abs(img_b - vid_b)
        total_rgb_diff += diff
        count += 1

    return total_rgb_diff / count

def format_timestamp(secs):
    return '[{}]'.format(
        str(datetime.timedelta(seconds=sec)),
    )

def remove_video_file(vid_filepath):
    if not os.path.exists(vid_filepath):
        return

    try:
        os.remove(vid_filepath)
    except Exception as e:
        print('error removing {}'.format(vid_filepath), e)
        sys.exit(1)

def mask_filepaths_to_title(mask_filepath0, mask_filepath1):
    if '-left.' in mask_filepath0:
        left_filepath = mask_filepath0
        right_filepath = mask_filepath1
    else:
        left_filepath = mask_filepath1
        right_filepath = mask_filepath0

    char_name = lambda s: os.path.basename(s).split('-')[0]
    return '{} vs {}'.format(
        char_name(left_filepath),
        char_name(right_filepath),
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse GGXRD youtube video for matches')
    parser.add_argument(
        'youtube_url',
        type=str,
        help='youtube URL (e.g. https://www.youtube.com/watch?v=fOvG_TfnCVo)',
    )
    parser.add_argument(
        '-t',
        '--tmp-filepath',
        type=str,
        default='video.webm',
        help='filepath to save temp downloaded youtube video '\
        '(e.g. /var/tmp/video)',
    )
    parser.add_argument(
        '-o',
        '--output-filepath',
        type=str,
        default='matches.html',
        help='filepath to output parsed matches html file '\
        '(e.g. matches.html)',
    )
    parser.add_argument(
        '--already-downloaded',
        action='store_true',
        help='use existing youtube video file already on disk',
    )
    parser.add_argument(
        '--keep-tmp-video',
        action='store_true',
        help='keep the temp downloaded youtube video file after parsing',
    )
    args = parser.parse_args()

    # Download youtube video
    ###########################################################################
    if not args.already_downloaded:
        remove_video_file(args.tmp_filepath)
        subprocess.check_call(
            'youtube-dl --format worstvideo --no-continue --output {} '
            '"{}"'.format(
                args.tmp_filepath,
                args.youtube_url,
            ),
            shell=True,
        )


    # Find match start timestamps
    ###########################################################################
    clip = VideoFileClip(args.tmp_filepath, audio=False)
    sec_matches = []
    match_titles = []

    sec = 0
    while sec < int(clip.duration) - SKIP_SECS:
        clip_frame_rgb = clip.get_frame(sec).flatten()

        if compare_rgb(VS_MASK, clip_frame_rgb) < RGB_DIFF_THRESHOLD:
            next_clip_frame_rgb = clip.get_frame(sec + 1).flatten()

            press_start_rgb_diff = compare_rgb(PRESS_START_MASK, next_clip_frame_rgb)
            insert_coin_rgb_diff = compare_rgb(INSERT_COIN_MASK, next_clip_frame_rgb)
            not_demo_mode = (
                press_start_rgb_diff >= RGB_DIFF_THRESHOLD and
                insert_coin_rgb_diff >= RGB_DIFF_THRESHOLD
            )

            not_training_mode = all(
                compare_rgb(mask, clip_frame_rgb) >= TIME_LIMIT_RGB_DIFF_THRESHOLD
                for mask in TIME_LIMIT_MASKS
            )

            if not_demo_mode and not_training_mode:
                # Figure out match characters
                ###############################################################
                clip_frame_rgb = clip.get_frame(sec).flatten()
                mask_diffs = []

                for char_mask in CHAR_MASKS:
                    diff = compare_rgb(char_mask, clip_frame_rgb)
                    mask_diffs.append((diff, char_mask))

                sorted_mask_diffs = sorted(mask_diffs, key=lambda md: md[0])

                if (
                    sorted_mask_diffs[0][0] < CHAR_RGB_DIFF_THRESHOLD and
                    sorted_mask_diffs[1][0] < CHAR_RGB_DIFF_THRESHOLD
                ):
                    sec_matches.append(sec)
                    match_titles.append(
                        mask_filepaths_to_title(
                            sorted_mask_diffs[0][1].filepath,
                            sorted_mask_diffs[1][1].filepath,
                        ),
                    )
                    print(format_timestamp(sec), match_titles[-1])

            sec += SKIP_SECS
        else:
            sec += 1


    # Write matches file
    ###########################################################################
    video_id = subprocess.check_output(
        'youtube-dl --get-id --no-warnings {}'.format(args.youtube_url),
        shell=True,
    ).decode('utf-8').rstrip()

    stripped_url = re.sub(r'\?t=\d+', '?', args.youtube_url)
    stripped_url = re.sub(r'&t=\d+', '', stripped_url)

    with open(args.output_filepath, 'w') as f:
        f.write(
            '<iframe width="480" height="360" '
            'src="https://www.youtube.com/embed/{}" frameborder="0" '
            'allow="autoplay; encrypted-media" allowfullscreen>'
            '</iframe><br>\n'.format(video_id),
        )

        for sec, title in zip(sec_matches, match_titles):
            f.write(
                '<a href={}#t={}>{} {}</a><br>\n'.format(
                    stripped_url,
                    sec,
                    format_timestamp(sec),
                    title,
                ),
            )
        f.write('<br><hr><br>\n')

    if not args.keep_tmp_video and not args.already_downloaded:
        remove_video_file(args.tmp_filepath)
