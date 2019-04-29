#!/usr/bin/env python3
import argparse
import collections
import datetime
import itertools
import os
import re
import subprocess
import sys

from PIL import Image
from PIL import ImageChops
from PIL import ImageStat
from moviepy.video.io.VideoFileClip import VideoFileClip
import imagehash


PRINT_REJECTED_MATCHES = True
DATA_DIRPATH = os.path.join(
    os.path.dirname(__file__),
    'data',
)
CLIP_FRAME_BUFFER_MAX_SECS = 8
TARGET_RESOLUTION = (144, 256)
SKIP_SECS = 5
SEEK_SECS = 0.25


def load_image(filename, with_alpha=True):
    img = Image.open(
        '{}/images/{}'.format(DATA_DIRPATH, filename),
    )
    return img if with_alpha else img.convert('RGB')

def load_image_mask(filename):
    return Image.open(
        '{}/masks/{}'.format(DATA_DIRPATH, filename),
    ).convert('1')

def load_char_images(dirname, side):
    filename_suffix = '{}.png'.format(side)
    box = CHAR_LEFT_IMAGE_BOX if side == '-left' else CHAR_RIGHT_IMAGE_BOX
    char_images = {}
    for filename in os.listdir('{}/{}'.format(DATA_DIRPATH, dirname)):
        if filename.endswith(filename_suffix):
            char_name = os.path.splitext(filename)[0]
            img = Image.open(
                '{}/{}/{}'.format(DATA_DIRPATH, dirname, filename)
            ).convert('RGB')
            char_images[char_name] = img.crop(box=box)
    return char_images


VS_IMAGE_BOX = [102, 39, 102+52, 39+51]
VS_IMAGE_V_BOX = [107, 40, 107+17, 40+38]
VS_IMAGE_S_BOX = [128, 52, 128+20, 52+36]
VS_IMAGE = load_image('vs.png', with_alpha=False)
VS_IMAGE_HASH = imagehash.average_hash(VS_IMAGE.crop(VS_IMAGE_BOX))
VS_IMAGE_V_HASH = imagehash.average_hash(VS_IMAGE.crop(VS_IMAGE_V_BOX))
VS_IMAGE_S_HASH = imagehash.average_hash(VS_IMAGE.crop(VS_IMAGE_S_BOX))
VS_IMAGE_HASH_THRESHOLD = 20
VS_INTERRUPTED_SECS_DIFF_THRESHOLD = 34/30  # 34 frames @30fps
VS_IMAGE_MASK = load_image_mask('vs.png')
VS_IMAGE_HISTOGRAM = VS_IMAGE.histogram(mask=VS_IMAGE_MASK)
VS_IMAGE_HISTOGRAM_DIFF_THRESHOLD = 0.3

VARIOUS_MODE_IMAGES = [
    load_image('demo-banner.png'),
    load_image('time-limit-left.png'),
    load_image('time-limit-right.png'),
    load_image('insert-coins-left.png'),
    load_image('insert-coins-right.png'),
    load_image('episode-mode-left.png'),
    load_image('episode-mode-right.png'),
    load_image('stage-left.png'),
    load_image('stage-right.png'),
]
VARIOUS_MODE_IMAGE_RGB_DIFF_THRESHOLD = 50

MOM_MODE_IMAGES = [
    load_image('mom-display-left.png'),
    load_image('mom-display-right.png'),
]
MOM_MODE_IMAGE_RGB_DIFF_THRESHOLD = 75

CHAR_LEFT_IMAGE_BOX = [7, 24, 7+91, 24+40]
CHAR_RIGHT_IMAGE_BOX = [156, 24, 156+91, 24+40]
CHAR_LEFT_IMAGES = load_char_images('char-images', '-left')
CHAR_RIGHT_IMAGES = load_char_images('char-images', '-right')
CHAR_LEFT_EARLY_IMAGES = load_char_images('char-images-early', '-left')
CHAR_RIGHT_EARLY_IMAGES = load_char_images('char-images-early', '-right')
CHAR_IMAGE_HASH_FUNCTIONS = [
    imagehash.average_hash,
    imagehash.phash,
    imagehash.dhash,
    imagehash.whash,
]
CHAR_IMAGE_HASH_THRESHOLD = 80

MAX_ALPHA = 255
image_with_alpha_pixel_count_cache = {}


def clip_frame_to_image(clip_frame):
    return Image.fromarray(clip_frame.astype('uint8'), 'RGB')

def compare_rgb(img_with_alpha, img):
    img_composite = Image.alpha_composite(img.convert('RGBA'), img_with_alpha).convert('RGB')
    img_diff = ImageChops.difference(img_composite, img)
    total = sum(ImageStat.Stat(img_diff).sum)
    try:
        count = image_with_alpha_pixel_count_cache[img_with_alpha.filename]
    except Exception:
        count = ImageStat.Stat(img_with_alpha.getchannel('A').getdata()).sum[0] / MAX_ALPHA
        image_with_alpha_pixel_count_cache[img_with_alpha.filename] = count
    return total / count

def histogram_diff(hist1, hist2):
    return sum(min(v1, v2) for v1, v2 in zip(hist1, hist2)) / sum(hist2)

def format_timestamp(sec):
    return '[{}]'.format(
        datetime.timedelta(seconds=int(sec)),
    )

def format_title(char_left_key, char_right_key):
    char_name = lambda s: os.path.basename(s).split('-')[0]
    return '{} vs {}'.format(
        char_name(char_left_key),
        char_name(char_right_key),
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

def remove_video_file(vid_filepath):
    if not os.path.exists(vid_filepath):
        return

    try:
        os.remove(vid_filepath)
    except Exception as e:
        print('error removing {}'.format(vid_filepath), e)
        sys.exit(1)

def flatten(xs):
    return list(itertools.chain(*xs))


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

    clip = VideoFileClip(
        args.tmp_filepath,
        audio=False,
    )
    clip_frame0 = clip.get_frame(0)
    clip_resolution = (len(clip_frame0), len(clip_frame0[0]))
    if clip_resolution != TARGET_RESOLUTION:
        clip.reader.close()
        clip = VideoFileClip(
            args.tmp_filepath,
            audio=False,
            target_resolution=TARGET_RESOLUTION,
            resize_algorithm='fast_bilinear',
        )


    # Find match start timestamps
    ###########################################################################
    sec_clip_frames_buffer = collections.deque()
    vs_sec_clip_frames = []
    sec_matches = []
    match_titles = []
    next_sec = 0

    for sec, clip_frame in clip.iter_frames(with_times=True):
        while sec_clip_frames_buffer:
            (buffer_sec, _) = sec_clip_frames_buffer[0]
            if sec - buffer_sec > CLIP_FRAME_BUFFER_MAX_SECS:
                sec_clip_frames_buffer.popleft()
            else:
                break
        sec_clip_frames_buffer.append((sec, clip_frame))

        if sec < next_sec:
            continue

        clip_frame_img = clip_frame_to_image(clip_frame)

        # Detect VS splash screen start/continuing
        vs_img_hash_diff = imagehash.average_hash(clip_frame_img.crop(box=VS_IMAGE_BOX)) - VS_IMAGE_HASH
        is_vs_sec_clip_frame_start = (
            not vs_sec_clip_frames and
            vs_img_hash_diff < VS_IMAGE_HASH_THRESHOLD and
            imagehash.average_hash(clip_frame_img.crop(box=VS_IMAGE_V_BOX)) - VS_IMAGE_V_HASH < VS_IMAGE_HASH_THRESHOLD and
            imagehash.average_hash(clip_frame_img.crop(box=VS_IMAGE_S_BOX)) - VS_IMAGE_S_HASH < VS_IMAGE_HASH_THRESHOLD
        )
        set_vs_sec_clip_frame = False
        if is_vs_sec_clip_frame_start or (
            vs_sec_clip_frames and
            vs_img_hash_diff < VS_IMAGE_HASH_THRESHOLD and
            histogram_diff(clip_frame_img.histogram(mask=VS_IMAGE_MASK), VS_IMAGE_HISTOGRAM) > VS_IMAGE_HISTOGRAM_DIFF_THRESHOLD
        ):
            vs_sec_clip_frames.append((sec, clip_frame))
            set_vs_sec_clip_frame = True

        # Process VS splash screen
        if vs_sec_clip_frames and not set_vs_sec_clip_frame:
            # Ignore various 1-player modes
            is_1p_mode = False
            for prev_sec, prev_clip_frame in sec_clip_frames_buffer:
                prev_clip_frame_img = clip_frame_to_image(prev_clip_frame)
                for img in VARIOUS_MODE_IMAGES:
                    img_diff = compare_rgb(img, prev_clip_frame_img)
                    if img_diff < VARIOUS_MODE_IMAGE_RGB_DIFF_THRESHOLD:
                        if PRINT_REJECTED_MATCHES:
                            print('{}\t\t\tREJECT ({}) | <{}>'.format(
                                format_timestamp(prev_sec),
                                os.path.splitext(os.path.basename(img.filename))[0],
                                img_diff,
                            ))
                        is_1p_mode = True
                        break
                if is_1p_mode:
                    break
            if is_1p_mode:
                vs_sec_clip_frames = []
                next_sec = sec + SKIP_SECS
                continue

            (vs_sec, vs_clip_frame) = vs_sec_clip_frames[-1]
            (early_vs_sec, early_vs_clip_frame) = vs_sec_clip_frames[0]
            vs_sec_clip_frames = []
            vs_clip_frame_img = clip_frame_to_image(vs_clip_frame)

            # Ignore M.O.M. matches
            if any(
                compare_rgb(img, vs_clip_frame_img) < MOM_MODE_IMAGE_RGB_DIFF_THRESHOLD
                for img in MOM_MODE_IMAGES
            ):
                if PRINT_REJECTED_MATCHES:
                    print('{}\t\t\tREJECT (M.O.M. mode)'.format(
                        format_timestamp(vs_sec),
                    ))
                next_sec = vs_sec + SKIP_SECS
                continue


            # Figure out match characters
            ###############################################################
            def determine_side_char(char_side_imgs, char_side_img_box, char_clip_frame_img):
                hash_diffs = collections.defaultdict(int)
                char_clip_frame_img_cropped = char_clip_frame_img.crop(box=char_side_img_box)

                for imagehash_fn in CHAR_IMAGE_HASH_FUNCTIONS:
                    char_clip_frame_img_hash = imagehash_fn(char_clip_frame_img_cropped)
                    for char_key, char_side_img in char_side_imgs.items():
                        hash_diff = char_clip_frame_img_hash - imagehash_fn(char_side_img)
                        hash_diffs[char_key] += hash_diff

                return sorted(
                    (
                        (char_key, hash_diff)
                        for char_key, hash_diff
                        in hash_diffs.items()
                    ),
                    key=lambda kv: kv[1],
                )[0]

            if vs_sec - early_vs_sec >= VS_INTERRUPTED_SECS_DIFF_THRESHOLD:
                char_left_imgs = CHAR_LEFT_IMAGES
                char_right_imgs = CHAR_RIGHT_IMAGES
                char_clip_frame_img = vs_clip_frame_img
                reject_print_reason_suffix = ''
            else:
                char_left_imgs = CHAR_LEFT_EARLY_IMAGES
                char_right_imgs = CHAR_RIGHT_EARLY_IMAGES
                char_clip_frame_img = clip_frame_to_image(early_vs_clip_frame)
                reject_print_reason_suffix = '-early'
                #print('{}\t\t\t***EARLY*** <{}>'.format(format_timestamp(early_vs_sec), vs_sec - early_vs_sec))

            is_above_char_threshold = False
            char_keys = []
            for char_side_imgs, char_side_img_box in [
                (char_left_imgs, CHAR_LEFT_IMAGE_BOX),
                (char_right_imgs, CHAR_RIGHT_IMAGE_BOX),
            ]:
                char_key, hash_diff = determine_side_char(
                    char_side_imgs,
                    char_side_img_box,
                    char_clip_frame_img,
                )
                if hash_diff < CHAR_IMAGE_HASH_THRESHOLD:
                    char_keys.append(char_key)
                else:
                    if PRINT_REJECTED_MATCHES:
                        print('{}\t\t\tREJECT (char threshold{}) | <{}, {}>'.format(
                            format_timestamp(vs_sec),
                            reject_print_reason_suffix,
                            char_key,
                            hash_diff,
                        ))
                    is_above_char_threshold = True
                    break
            if is_above_char_threshold:
                continue

            sec_matches.append(early_vs_sec)
            title = format_title(*char_keys)
            match_titles.append(title)
            next_sec = vs_sec + SKIP_SECS
            print(format_timestamp(early_vs_sec), title)
        elif not vs_sec_clip_frames:
            next_sec = sec + SEEK_SECS

    clip.reader.close()


    # Write matches file
    ###########################################################################
    stripped_url = re.sub(r'\?t=\d+', '?', args.youtube_url)
    stripped_url = re.sub(r'&t=\d+', '', stripped_url)
    stripped_url = re.sub(r'#t=\d+', '', stripped_url)

    with open(args.output_filepath, 'w') as f:
        f.write('<ol reversed>')
        for sec, title in zip(sec_matches[::-1], match_titles[::-1]):
            f.write(
                '<li><a href={}#t={}>{} {}</a></li>\n'.format(
                    stripped_url,
                    sec,
                    format_timestamp(sec),
                    title,
                ),
            )
        f.write('</ol><br><hr>\n')

    if not args.keep_tmp_video and not args.already_downloaded:
        remove_video_file(args.tmp_filepath)
