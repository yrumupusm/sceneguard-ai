"""CPU-only still renderer, run in the existing local CV environment.

The web process passes an already authorized video FD and a small JSON request.
No paths, model loading, tracking, flow or inference are accepted by this helper.
"""
from fractions import Fraction
import json
import os
import sys


def render(fd, item):
    import av
    import cv2
    cv2.setNumThreads(1)
    target = Fraction(str(item['frame']['playback_seconds']))
    with os.fdopen(fd, 'rb') as source, av.open(source) as container:
        stream = container.streams.video[0]
        stream.codec_context.thread_count = 1
        container.seek(max(0, int(target / stream.time_base)), stream=stream, backward=True)
        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            at = frame.pts * frame.time_base
            if abs(float(at - target)) <= 1e-7:
                bgr = frame.to_ndarray(format='bgr24')
                break
            if at > target + Fraction(1, 10000000):
                raise ValueError('Exact saved playback frame missing')
        else:
            raise ValueError('Exact saved playback frame missing')
    height, width = bgr.shape[:2]
    for box in item['boxes']:
        x1, y1, x2, y2 = box['bbox']
        cv2.rectangle(bgr, (round(x1 * width), round(y1 * height)),
                      (round(x2 * width), round(y2 * height)), (0, 210, 255), 3)
    # A modest still, preserving the original frame's aspect ratio.
    if width > 1280:
        bgr = cv2.resize(bgr, (1280, round(height * 1280 / width)))
    ok, encoded = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise ValueError('JPEG encoding failed')
    return encoded.tobytes()


if __name__ == '__main__':
    sys.stdout.buffer.write(render(int(sys.argv[1]), json.load(sys.stdin)))
