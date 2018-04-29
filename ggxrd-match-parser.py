#!/usr/bin/env python
import argparse
import datetime
import os
import re
import subprocess
import sys

from PIL import Image
from moviepy.video.io.VideoFileClip import VideoFileClip


MASKS_DIRPATH = os.path.join(
    os.path.dirname(__file__),
    'masks',
)
TARGET_RESOLUTION = (144, 256)
RGB_DIFF_THRESHOLD = 75
CHAR_RGB_DIFF_THRESHOLD = 125
SKIP_SECS = 20
SEEK_SECS = 0.5


class Mask(object):
    def __init__(self, filepath):
        self.filepath = filepath
        self.img_data = list(
            Image.open(
                '{}/{}'.format(MASKS_DIRPATH, filepath),
            ).getdata(),
        )

VS_MASK = Mask('vs.png')

DEMO_MASKS = [
    Mask('press-start.png'),
    Mask('insert-coins-center.png'),
    Mask('insert-coins-bot-center.png'),
    Mask('character-usage.png'),
]

TRAINING_MASKS = [
    Mask('time-limit-left.png'),
    Mask('time-limit-right.png'),
]

MOM_MODE_MASKS = [
    Mask('mom-display-left.png'),
    Mask('mom-display-right.png'),
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
        str(datetime.timedelta(seconds=int(sec))),
    )

def remove_video_file(vid_filepath):
    if not os.path.exists(vid_filepath):
        return

    try:
        os.remove(vid_filepath)
    except Exception as e:
        print('error removing {}'.format(vid_filepath), e)
        sys.exit(1)

def char_mask_filepaths_to_title(mask_filepath0, mask_filepath1):
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

def get_video_id(url):
    for m in [
        re.match(r'.+youtu\.be/(?P<id>[^?&#]+)', url),
        re.match(r'.+/watch\?v=(?P<id>[^&#]+)', url),
        re.match(r'.+/v/(?P<id>[^?&#]+)', url),
    ]:
        if m:
            return m.group('id')
    return ''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse GGXRD youtube video for matches')
    parser.add_argument(
        'youtube_url',
        type=str,
        help='youtube video URL (e.g. https://www.youtube.com/watch?v=fOvG_TfnCVo)',
    )
    parser.add_argument(
        '-t',
        '--tmp-filepath',
        type=str,
        default='video.webm',
        help='filepath to save temp downloaded youtube video '\
        '(e.g. ./youtube-vid)',
    )
    parser.add_argument(
        '-o',
        '--output-filepath',
        type=str,
        default='matches.html',
        help='filepath to output parsed matches html file '\
        '(e.g. ./matches.html)',
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
    clip = VideoFileClip(
        args.tmp_filepath,
        audio=False,
        target_resolution=TARGET_RESOLUTION,
        resize_algorithm='fast_bilinear',
    )
    sec_matches = []
    match_titles = []
    next_sec = 0

    for sec, clip_frame in clip.iter_frames(with_times=True):
        if sec < next_sec:
            continue

        clip_frame_rgb = clip_frame.flatten()

        if any(
            compare_rgb(mask, clip_frame_rgb) < RGB_DIFF_THRESHOLD
            for mask in DEMO_MASKS
        ):
            next_sec = sec + SKIP_SECS
            continue

        if compare_rgb(VS_MASK, clip_frame_rgb) < RGB_DIFF_THRESHOLD:
            training_mode = any(
                compare_rgb(mask, clip_frame_rgb) < RGB_DIFF_THRESHOLD
                for mask in TRAINING_MASKS
            )

            mom_mode = any(
                compare_rgb(mask, clip_frame_rgb) < RGB_DIFF_THRESHOLD
                for mask in MOM_MODE_MASKS
            )

            if training_mode or mom_mode:
                next_sec = sec + SKIP_SECS
                continue

            # Figure out match characters
            ###############################################################
            mask_diffs = []

            for char_mask in CHAR_MASKS:
                diff = compare_rgb(char_mask, clip_frame_rgb)
                mask_diffs.append((diff, char_mask))

            sorted_mask_diffs = sorted(mask_diffs, key=lambda md: md[0])

            if (
                sorted_mask_diffs[0][0] < CHAR_RGB_DIFF_THRESHOLD and
                sorted_mask_diffs[1][0] < CHAR_RGB_DIFF_THRESHOLD
            ):
                sec_matches.append(int(sec))
                match_titles.append(
                    char_mask_filepaths_to_title(
                        sorted_mask_diffs[0][1].filepath,
                        sorted_mask_diffs[1][1].filepath,
                    ),
                )
                print(format_timestamp(sec), match_titles[-1])

            next_sec = sec + SKIP_SECS
        else:
            next_sec = sec + SEEK_SECS


    # Write matches file
    ###########################################################################
    stripped_url = re.sub(r'\?t=\d+', '?', args.youtube_url)
    stripped_url = re.sub(r'&t=\d+', '', stripped_url)
    stripped_url = re.sub(r'#t=\d+', '', stripped_url)

    with open(args.output_filepath, 'w') as f:
        f.write(
            '<iframe width="480" height="360" '
            'src="https://www.youtube.com/embed/{}" frameborder="0" '
            'allow="autoplay; encrypted-media" allowfullscreen>'
            '</iframe><br>\n'.format(
                get_video_id(args.youtube_url),
            ),
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
