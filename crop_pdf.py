#! /usr/bin/env python

import sys
import subprocess
import re
import numpy

def get_raw_bbox(inf):
    output = subprocess.check_output(["pdfcrop", "--verbose", inf, "/dev/null"])
    res = {}
    pattern = r'\s*\* Page (\d+): (\d+) (\d+) (\d+) (\d+)\s*'
    for line in output.split('\n'):
        match = re.match(pattern, line)
        if not match:
            continue
        page_no = int(match.groups()[0])
        bbox = [int(match.groups()[1]), int(match.groups()[2]), int(match.groups()[3]), int(match.groups()[4])]
        res[page_no] = bbox
    return res

def get_median_bbox(raw_bboxes):
    odd_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 1])
    odd_median_bbox = [int(e) for e in numpy.median(odd_bboxes, 0)]

    even_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 0])
    even_median_bbox = [int(e) for e in numpy.median(even_bboxes, 0)]

    return odd_median_bbox, even_median_bbox

def get_max_bbox(raw_bboxes):
    odd_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 1])
    odd_max_bbox = [numpy.min(odd_bboxes[:,0]), numpy.min(odd_bboxes[:,1]), numpy.max(odd_bboxes[:,2]), numpy.max(odd_bboxes[:,3])]

    even_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 0])
    even_max_bbox = [numpy.min(even_bboxes[:,0]), numpy.min(even_bboxes[:,1]), numpy.max(even_bboxes[:,2]), numpy.max(even_bboxes[:,3])]


    return odd_max_bbox, even_max_bbox

def get_best_bbox(raw_bboxes):
    odd_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 1])
    odd_best_bbox = [numpy.percentile(odd_bboxes[:,0], 25), numpy.percentile(odd_bboxes[:,1], 25), numpy.percentile(odd_bboxes[:,2], 75), numpy.percentile(odd_bboxes[:,3], 75)]

    even_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 0])
    even_best_bbox = [numpy.percentile(even_bboxes[:,0], 25), numpy.percentile(even_bboxes[:,1], 25), numpy.percentile(even_bboxes[:,2], 75), numpy.percentile(even_bboxes[:,3], 75)]


    return odd_best_bbox, even_best_bbox


def crop(inf, outf, odd_bbox, even_bbox):
    subprocess.check_output(["pdfcrop",
                             "--verbose",
                             "--bbox-odd", "{} {} {} {}".format(*odd_bbox),
                             "--bbox-even", "{} {} {} {}".format(*even_bbox),
                             inf, outf])

if __name__ == "__main__":
    inf = sys.argv[1]
    outf = sys.argv[2]

    raw_bboxes = get_raw_bbox(inf)
    # odd_bbox, even_bbox = get_median_bbox(raw_bboxes)
    odd_bbox, even_bbox = get_best_bbox(raw_bboxes)
    crop(inf, outf, odd_bbox, even_bbox)
