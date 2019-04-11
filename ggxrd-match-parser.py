#!/usr/bin/env python
import argparse
import datetime
import itertools
import json
import os
import re
import subprocess
import sys

from PIL import Image
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.io.VideoFileClip import VideoFileClip


DATA_DIRPATH = os.path.join(
    os.path.dirname(__file__),
    'data',
)
AUDIO_FILEPATH_SUFFIX = '.audio'
TARGET_RESOLUTION = (144, 256)
MASK_RGB_DIFF_THRESHOLD = 75
SKIP_SECS = 5
SEEK_SECS = 0.5
VS_AUDIO_FRAME_THRESHOLD = 0.001
HISTOGRAM_DIFF_THRESHOLD = 0.7
CHAR_HISTOGRAM_DIFF_DELTA_THRESHOLD = 0.03

VS_BW_IMG = Image.open(
    '{}/vs-bw.png'.format(DATA_DIRPATH),
).convert('1')
VS_HISTOGRAM = Image.open(
    '{}/vs.png'.format(DATA_DIRPATH),
).convert('RGB').histogram(mask=VS_BW_IMG)
CHAR_LEFT_BW_IMG = Image.open(
    '{}/char-left-bw.png'.format(DATA_DIRPATH),
).convert('1')
CHAR_RIGHT_BW_IMG = Image.open(
    '{}/char-right-bw.png'.format(DATA_DIRPATH),
).convert('1')

class Mask(object):
    def __init__(self, filepath):
        self.filepath = filepath
        self.img_data = list(
            Image.open(
                '{}/masks/{}'.format(DATA_DIRPATH, filepath),
            ).convert('RGB').getdata(),
        )

TRAINING_MASKS = [
    Mask('time-limit-left.png'),
    Mask('time-limit-right.png'),
]

MOM_MODE_MASKS = [
    Mask('mom-display-left.png'),
    Mask('mom-display-right.png'),
]

CHAR_LEFT_HISTOGRAMS = {}
CHAR_RIGHT_HISTOGRAMS = {}
CHAR_LEFT_IMAGES = {}
CHAR_RIGHT_IMAGES = {}
for filepath in os.listdir('{}/chars'.format(DATA_DIRPATH)):
    char_name = os.path.splitext(filepath)[0]
    if filepath.endswith('.json'):
        with open('{}/chars/{}'.format(DATA_DIRPATH, filepath), 'r') as f:
            histogram = json.load(f)
            if char_name.endswith('-left'):
                CHAR_LEFT_HISTOGRAMS[char_name] = histogram
            else:
                CHAR_RIGHT_HISTOGRAMS[char_name] = histogram
    elif filepath.endswith('.png'):
        img = Image.open('{}/chars/{}'.format(DATA_DIRPATH, filepath))
        if char_name.endswith('-left'):
            CHAR_LEFT_IMAGES[char_name] = img
        else:
            CHAR_RIGHT_IMAGES[char_name] = img#"""


def flatten(xs):
    return list(itertools.chain(*xs))

def histogram_diff(hist1, hist2):
    return sum(min(v1, v2) for v1, v2 in zip(hist1, hist2)) / sum(hist2)

def compare_rgb(mask_rgb, vid_rgb):
    total_rgb_diff = 0
    count = 0

    for i, (img_r, img_g, img_b) in enumerate(mask_rgb):
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

def remove_audiovideo_file(audiovid_filepath):
    if not os.path.exists(audiovid_filepath):
        return

    try:
        os.remove(audiovid_filepath)
    except Exception as e:
        print('error removing {}'.format(audiovid_filepath), e)
        sys.exit(1)

def format_title(char_left, char_right):
    left_filepath = char_left
    right_filepath = char_right

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
        remove_audiovideo_file(args.tmp_filepath)
        subprocess.check_call(
            'youtube-dl --format worstvideo --no-continue --output {} '
            '"{}"'.format(
                args.tmp_filepath,
                args.youtube_url,
            ),
            shell=True,
        )

    # Download youtube audio
    ###########################################################################
    if not args.already_downloaded:
        audio_filepath = args.tmp_filepath + AUDIO_FILEPATH_SUFFIX
        remove_audiovideo_file(audio_filepath)
        subprocess.check_call(
            'youtube-dl --format worstaudio --no-continue --output {} '
            '"{}"'.format(
                audio_filepath,
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

    with AudioFileClip(args.tmp_filepath + AUDIO_FILEPATH_SUFFIX) as audio_clip:
        for sec, clip_frame in clip.iter_frames(with_times=True):
            if sec < next_sec:
                continue

            clip_frame_img = Image.fromarray(clip_frame.astype('uint8'), 'RGB')
            clip_frame_vs_histogram = clip_frame_img.histogram(mask=VS_BW_IMG)

            if histogram_diff(clip_frame_vs_histogram, VS_HISTOGRAM) >= HISTOGRAM_DIFF_THRESHOLD:
                is_demo_mode = all(
                    abs(x) < VS_AUDIO_FRAME_THRESHOLD
                    for x in audio_clip.get_frame(sec)
                )

                clip_frame_rgb = clip_frame.flatten()
                is_training_mode = any(
                    compare_rgb(mask.img_data, clip_frame_rgb) < MASK_RGB_DIFF_THRESHOLD
                    for mask in TRAINING_MASKS
                )

                is_mom_mode = any(
                    compare_rgb(mask.img_data, clip_frame_rgb) < MASK_RGB_DIFF_THRESHOLD
                    for mask in MOM_MODE_MASKS
                )

                if is_demo_mode or is_training_mode or is_mom_mode:
                    next_sec = sec + SKIP_SECS
                    continue

                # Figure out match characters
                ###############################################################
                char_left_histogram = clip_frame_img.histogram(mask=CHAR_LEFT_BW_IMG)
                char_right_histogram = clip_frame_img.histogram(mask=CHAR_RIGHT_BW_IMG)

                char_left_histogram_diffs = [
                    (histogram_diff(char_left_histogram, histogram), char_name)
                    for char_name, histogram in CHAR_LEFT_HISTOGRAMS.items()
                ]
                char_right_histogram_diffs = [
                    (histogram_diff(char_right_histogram, histogram), char_name)
                    for char_name, histogram in CHAR_RIGHT_HISTOGRAMS.items()
                ]

                sorted_left_histogram_diffs = sorted(char_left_histogram_diffs, key=lambda hd: hd[0], reverse=True)
                sorted_right_histogram_diffs = sorted(char_right_histogram_diffs, key=lambda hd: hd[0], reverse=True)

                if sorted_left_histogram_diffs[0][0] < HISTOGRAM_DIFF_THRESHOLD or sorted_right_histogram_diffs[0][0] < HISTOGRAM_DIFF_THRESHOLD:
                    continue

                def rgb_fallback_char_match(char_side_bw_img, char_side_images):
                    side_img = char_side_bw_img.convert('RGB')
                    side_img.paste(clip_frame_img, mask=char_side_bw_img)
                    rgb_diffs = [
                        (
                            compare_rgb(
                                list(side_img.getdata()),
                                flatten(list(char_img.getdata())),
                            ),
                            char_name,
                        )
                        for char_name, char_img
                        in char_side_images.items()
                    ]
                    sorted_rgb_diffs = sorted(rgb_diffs, key=lambda h: h[0])
                    return sorted_rgb_diffs[0][1]

                left_char = sorted_left_histogram_diffs[0][1]
                right_char = sorted_right_histogram_diffs[0][1]
                left_hist_diff_delta = sorted_left_histogram_diffs[0][0] - sorted_left_histogram_diffs[1][0]
                right_hist_diff_delta = sorted_right_histogram_diffs[0][0] - sorted_right_histogram_diffs[1][0]

                if left_hist_diff_delta <= CHAR_HISTOGRAM_DIFF_DELTA_THRESHOLD:
                    left_char = rgb_fallback_char_match(CHAR_LEFT_BW_IMG, CHAR_LEFT_IMAGES)
                if right_hist_diff_delta <= CHAR_HISTOGRAM_DIFF_DELTA_THRESHOLD:
                    right_char = rgb_fallback_char_match(CHAR_RIGHT_BW_IMG, CHAR_RIGHT_IMAGES)

                sec_matches.append(int(sec))
                title = format_title(left_char, right_char)
                match_titles.append(title)
                print(format_timestamp(sec), title)

                next_sec = sec + SKIP_SECS
            else:
                next_sec = sec + SEEK_SECS
    clip.reader.close()


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
        remove_audiovideo_file(args.tmp_filepath)
        remove_audiovideo_file(args.tmp_filepath + AUDIO_FILEPATH_SUFFIX)
