#! /usr/bin/env python

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfpage import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTFigure

from collections import defaultdict
import sys
import subprocess
import re
import numpy

def merge_bboxes(b1, b2):
    if not b1:
        return b2
    elif not b2:
        return b1
    else:
        return [
            int(min(b1[0], b2[0])),
            int(min(b1[1], b2[1])),
            int(max(b1[2], b2[2])),
            int(max(b1[3], b2[3]))
            ]


def get_raw_bbox(inf):
    # Open a PDF file.
    fp = open(inf, 'rb')
    # Create a PDF parser object associated with the file object.
    parser = PDFParser(fp)
    # Create a PDF document object that stores the document structure.
    # Supply the password for initialization.
    document = PDFDocument(parser)
    # Check if the document allows text extraction. If not, abort.
    if not document.is_extractable:
        raise PDFTextExtractionNotAllowed

    # Create a PDF resource manager object that stores shared resources.
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    textboxes = defaultdict(list)
    textcounts = defaultdict(int)
    page_counts = 0
    page_height = 0

    for i, page in enumerate(PDFPage.create_pages(document)):
        page_counts += 1
        page_no = i + 1
        bbox = [0, 0, 0, 0]
        interpreter.process_page(page)
        layout = device.get_result()
        for lt_obj in layout:
            if not isinstance(lt_obj, LTTextBox):
                continue
            text = lt_obj.get_text()
            max_text_width = max([len(l) for l in text.split('\n')])
            if max_text_width <= 3:
                continue
            textboxes[page_no].append(([lt_obj.bbox[0],
                                        lt_obj.bbox[1],
                                        lt_obj.bbox[2],
                                        lt_obj.bbox[3]],
                                       text))
            textcounts[text] +=1
    header_footers = []
    for k, v in textcounts.items():
        if k.startswith('Copy'):
            print k, v, page_counts
        if v >= page_counts/3:
            header_footers.append(k)
    print "header/footers: ", header_footers
    res = {}
    for page_no, tbs in textboxes.items():
        page_bb = None
        for bbox, text in tbs:
            if text in header_footers:
                continue
            page_bb = merge_bboxes(page_bb, bbox)

        if not page_bb:
            continue
        res[page_no] = page_bb
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
    LOWER = 10
    UPPER = 90
    odd_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 1])
    odd_best_bbox = [numpy.percentile(odd_bboxes[:,0], LOWER), numpy.percentile(odd_bboxes[:,1], LOWER), numpy.percentile(odd_bboxes[:,2], UPPER), numpy.percentile(odd_bboxes[:,3], UPPER)]

    even_bboxes = numpy.array([v for (k,v) in raw_bboxes.items() if k %2 == 0])
    even_best_bbox = [numpy.percentile(even_bboxes[:,0], LOWER), numpy.percentile(even_bboxes[:,1], LOWER), numpy.percentile(even_bboxes[:,2], UPPER), numpy.percentile(even_bboxes[:,3], UPPER)]


    return odd_best_bbox, even_best_bbox


def crop(inf, outf, odd_bbox, even_bbox):
    subprocess.check_output(["pdfcrop",
                             "--verbose",
                             "--bbox-odd", "{} {} {} {}".format(*odd_bbox),
                             "--bbox-even", "{} {} {} {}".format(*even_bbox),
                             inf, outf])

def equalize(b1, b2):
    h1, w1 = b1[2] - b1[0], b1[3] - b1[1]
    h2, w2 = b2[2] - b2[0], b2[3] - b2[1]
    h, w = max(h1, h2), max(w1, w2)

    return [b1[0], b1[1], b1[0] + h, b1[1] + w], [b2[0], b2[1], b2[0] + h, b2[1] + w]

if __name__ == "__main__":
    inf = sys.argv[1]
    outf = sys.argv[2]

    raw_bboxes = get_raw_bbox(inf)
    # odd_bbox, even_bbox = get_median_bbox(raw_bboxes)
    odd_bbox, even_bbox = get_best_bbox(raw_bboxes)
    odd_bbox, even_bbox = equalize(odd_bbox, even_bbox)

    print "Crop boxes for {}: ".format(inf), odd_bbox, even_bbox
    crop(inf, outf, odd_bbox, even_bbox)
