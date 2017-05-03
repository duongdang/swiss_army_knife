#! /usr/bin/env python
# -*- coding: utf-8 -*-

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfpage import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTFigure, LTLine, LTTextBoxHorizontal, LTTextLineHorizontal

from PyPDF2 import PdfFileWriter, PdfFileReader

from collections import defaultdict
import sys
import re
import numpy
import math

class DocumentLayout(object):
    def __init__(self, in_pdf = None):
        self.page_bboxes = {}
        self.useful_bboxes = {}
        self.text_obj_types = {}
        self.text_obj_counts = defaultdict(int)

        if in_pdf:
            self.parse_pdf(in_pdf)

    def parse_pdf(self, in_pdf):
        # Open a PDF file.
        fp = open(in_pdf, 'rb')
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
        laparams = LAParams(detect_vertical = True)
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)

        textboxes = defaultdict(list)
        textcounts = defaultdict(int)
        page_counts = 0

        ignored_obs_classes = set()
        processed_obs_classes = set()
        text_widths = []

        def process_text_box(page_no, bbox, text):
            # print "Processing for page {}: {} {}".format(page_no, bbox, text)
            lines = text.split('\n')
            text_length = len(lines)
            text_width = max([len(l) for l in lines])
            textboxes[page_no].append((bbox, text_length, text_width, text))
            text_widths.append(text_width)
            textcounts[text] +=1

        for i, page in enumerate(PDFPage.create_pages(document)):
            page_counts += 1
            page_no = i + 1

            interpreter.process_page(page)
            layout = device.get_result()

            cnt = 0

            curr_bbox = None
            curr_text = ""
            for lt_obj in layout:
                if not (isinstance(lt_obj, LTTextBoxHorizontal)
                        or isinstance(lt_obj, LTTextLineHorizontal)
                ):
                    ignored_obs_classes.add(lt_obj.__class__)
                    continue
                this_text = lt_obj.get_text().strip("\n")
                if "" == this_text:
                    continue
                processed_obs_classes.add(lt_obj.__class__)
                self.text_obj_counts[lt_obj.__class__] += 1
                # if a space exists between the current box and this box,
                # process the curr box and start new box
                dx = 0
                dy = 0
                if curr_bbox:
                    dx, dy = rect_distance(curr_bbox, lt_obj.bbox)
                # print "Processing", lt_obj
                # print "Distance was: {} from {} to {}".format(distance, curr_bbox, lt_obj.bbox)

                if max(dx, dy) > 20:
                    # print "New box"
                    process_text_box(page_no, curr_bbox, curr_text)
                    curr_bbox = lt_obj.bbox
                    curr_text = this_text
                else:
                    if dy > 3:
                        curr_text += "\n"
                    curr_text += this_text
                    # print "Merging {} and {}. Merged text: '{}'".format(curr_bbox, lt_obj.bbox, curr_text)
                    curr_bbox = merge_bboxes(curr_bbox, lt_obj.bbox)
                    # if this is the last box, also process it
                    # print "Merged to {}: {}".format(curr_bbox, curr_text)

            process_text_box(page_no, curr_bbox, curr_text)

        print "Ignored obj classes {}".format(ignored_obs_classes)
        print "Processed obj classes {}".format(processed_obs_classes)
        header_footers = []
        median_text_width = numpy.median(text_widths)
        print 'Median text_with: {}'.format(median_text_width)
        if median_text_width > 3:
            for k, v in textcounts.items():
                if v >= max(page_counts/3, 2):
                    header_footers.append(k)
        print "header/footers: ", header_footers
        res = {}

        for page_no, tbs in textboxes.items():
            alltext_bbox = None
            for i, (bbox, text_length, text_width, text) in enumerate(tbs):
                if bbox is None or bbox[2] - bbox[0] < 0.01:
                    continue
                elif text in header_footers:
                    continue
                elif median_text_width > 3 and text_width <= 3:
                    continue
                else:
                    # try:
                    #     print "Page no: {} Merging text {} from bbox: {}".format(page_no, text, bbox)
                    # except UnicodeError:
                    #     print "Page no: {} Merging text {} from bbox: {}".format(page_no, len(text), bbox)
                    alltext_bbox = merge_bboxes(alltext_bbox, bbox)


            if not alltext_bbox:
                continue
            self.useful_bboxes[page_no] = alltext_bbox
            self.page_bboxes[page_no] = layout.bbox
            self.text_obj_types[page_no] = processed_obs_classes
        return


    @classmethod
    def equalize(cls, b1, b2):
        h1, w1 = b1[2] - b1[0], b1[3] - b1[1]
        h2, w2 = b2[2] - b2[0], b2[3] - b2[1]
        h, w = max(h1, h2), max(w1, w2)

        return [b1[0], b1[1], b1[0] + h, b1[1] + w], [b2[0], b2[1], b2[0] + h, b2[1] + w]


    def get_median_bbox(self):
        odd_bboxes = numpy.array([v for (k,v) in self.useful_bboxes.items() if k %2 == 1])
        odd_median_bbox = [int(e) for e in numpy.median(odd_bboxes, 0)]

        even_bboxes = numpy.array([v for (k,v) in self.useful_bboxes.items() if k %2 == 0])
        even_median_bbox = [int(e) for e in numpy.median(even_bboxes, 0)]

        return odd_median_bbox, even_median_bbox

    def get_max_bbox(self):
        odd_bboxes = numpy.array([v for (k,v) in self.useful_bboxes.items() if k %2 == 1])
        odd_max_bbox = [numpy.min(odd_bboxes[:,0]), numpy.min(odd_bboxes[:,1]), numpy.max(odd_bboxes[:,2]), numpy.max(odd_bboxes[:,3])]

        even_bboxes = numpy.array([v for (k,v) in self.useful_bboxes.items() if k %2 == 0])
        even_max_bbox = [numpy.min(even_bboxes[:,0]), numpy.min(even_bboxes[:,1]), numpy.max(even_bboxes[:,2]), numpy.max(even_bboxes[:,3])]
        return odd_max_bbox, even_max_bbox

    @property
    def odd_page_size(self):
        odd_bboxes = numpy.array([v for (k,v) in self.page_bboxes.items() if k %2 == 1])
        return numpy.median(odd_bboxes[:,2]), numpy.median(odd_bboxes[:,3])

    @property
    def even_page_size(self):
        even_bboxes = numpy.array([v for (k,v) in self.page_bboxes.items() if k %2 == 0])
        return numpy.median(even_bboxes[:,2]), numpy.median(even_bboxes[:,3])

    @property
    def dominant_text_obj(self):
        return max(self.text_obj_counts, key=self.text_obj_counts.get)

    def get_best_bbox(self):
        LOWER = 10
        UPPER = 90

        if len(self.useful_bboxes) == 0:
            raise Exception('input bboxes are empty')

        odd_bboxes = numpy.array([v for (k,v) in self.useful_bboxes.items() if k %2 == 1])
        even_bboxes = numpy.array([v for (k,v) in self.useful_bboxes.items() if k %2 == 0])

        if len(even_bboxes) == 0:
            even_bboxes = odd_bboxes

        odd_best_bbox = [numpy.percentile(odd_bboxes[:,0], LOWER), numpy.percentile(odd_bboxes[:,1], LOWER), numpy.percentile(odd_bboxes[:,2], UPPER), numpy.percentile(odd_bboxes[:,3], UPPER)]
        even_best_bbox = [numpy.percentile(even_bboxes[:,0], LOWER), numpy.percentile(even_bboxes[:,1], LOWER), numpy.percentile(even_bboxes[:,2], UPPER), numpy.percentile(even_bboxes[:,3], UPPER)]

        if LTTextLineHorizontal == self.dominant_text_obj:
            print("LTTextLineHorizontal is dominant. Tweaking the bboxes, current value: {}, {}"
                   .format(odd_best_bbox, even_best_bbox))
            odd_best_bbox[2] = self.odd_page_size[0] - even_best_bbox[0]
            odd_best_bbox[3] += 20
            even_best_bbox[2] = self.even_page_size[0] - odd_best_bbox[0]
            even_best_bbox[3] += 20
            print("Tweaked value: {}, {}".format(odd_best_bbox, even_best_bbox))

        odd_best_bbox, even_best_bbox = self.equalize(odd_best_bbox, even_best_bbox)
        return odd_best_bbox, even_best_bbox


def merge_bboxes(b1, b2):
    if not b1:
        return b2
    elif not b2:
        return b1
    else:
        return [
            min(b1[0], b2[0]),
            min(b1[1], b2[1]),
            max(b1[2], b2[2]),
            max(b1[3], b2[3])
            ]
def seg_distance((x1, x2), (x3, x4)):
    if x1 > x3:
        return seg_distance((x3, x4), (x1, x2))
    if x1 > x2:
        return seg_distance((x2, x1), (x3, x4))
    if x3 > x4:
        return seg_distance((x1, x2), (x4, x3))
    ## now we are sure that x1 <= x2; x3 <= x4; x1 <= x3
    ## an overlap happens iif x3 is in between x1 and x2
    if x3 <= x2:
        return 0

    ## the only case left is x1 <= x2 <= x3 <= x4
    return x3 - x2

def rect_distance((x1, y1, x2, y2), (x3, y3, x4, y4)):
    dx = seg_distance((x1, x2), (x3, x4))
    dy = seg_distance((y1, y2), (y3, y4))
    return dx, dy

def crop(in_pdf, out_pdf, odd_bbox, even_bbox):
    inpdf = PdfFileReader(file(in_pdf, 'rb'))
    if inpdf.isEncrypted:
        print '{} is encrypted'.format(in_pdf)
        # inpdf._override_encryption = True
        # inpdf._flatten()
        inpdf.decrypt(b'')

    out = PdfFileWriter()
    page_no = 0
    for page in inpdf.pages:
        page_no += 1
        bbox = odd_bbox
        if page_no % 2 == 0:
            bbox = even_bbox
        page.mediaBox.lowerLeft  = bbox[0], bbox[1]
        page.mediaBox.upperRight = bbox[2], bbox[3]
        out.addPage(page)
    ous = file(out_pdf, 'wb')
    out.write(ous)
    ous.close()

if __name__ == "__main__":
    in_pdf = sys.argv[1]
    out_pdf = sys.argv[2]

    doc_layout = DocumentLayout(in_pdf)

    odd_bbox, even_bbox = doc_layout.get_best_bbox()

    print "Crop boxes for {}: ".format(in_pdf), odd_bbox, even_bbox
    crop(in_pdf, out_pdf, odd_bbox, even_bbox)
