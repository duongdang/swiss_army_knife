#! /usr/bin/env python

import argparse
import datetime
import pprint
from dateutil.relativedelta import relativedelta
import fnmatch
import os
import shutil
from PIL import Image
import exifread
import logging

ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(n/10%10!=1)*(n%10<4)*n%10::4])

class TimeInterval(object):
    def __init__(self, start, end, name):
        self.start = start
        self.end = end
        self.name = name

    def __repr__(self):
        return "{} [{}  {}]".format(self.name, self.start, self.end)

class Intervals(object):    
    def __init__(self, birth_dt):
        self.birth_dt = birth_dt
        self.intervals = []        
        self.make_intervals()

    def make_intervals(self):
        birth_d = datetime.datetime(self.birth_dt.year, self.birth_dt.month, self.birth_dt.day)
        curr_year = 0
        curr_dir = 0
        def dir_id():
            return "{:02d}{:02d}".format(curr_year, curr_dir)

        for curr_year in range(100):
            ## Special process for the first year
            y = curr_year
            # print "Processing year {}".format(y)
            curr_dir = 0
            if y == 0:
                self.intervals.append(
                    TimeInterval(self.birth_dt,
                                self.birth_dt + relativedelta(hours = 6),
                                 '{}_Birth'.format(dir_id())))

                for i in range(1,7):
                    curr_dir += 1
                    end = birth_d + relativedelta(days = i + 1) - relativedelta(seconds = 1)            
                    self.intervals.append(
                        TimeInterval(self.intervals[-1].end + relativedelta(seconds = 1),
                                     end,
                                    '{}_{}_Day{}'.format(dir_id(), i, 's' if i > 1 else '')))
                for i in range(1,5):
                    curr_dir += 1
                    if i < 4:
                        end = birth_d + relativedelta(days = 7*(i+1)) - relativedelta(seconds = 1)
                    else:
                        end = birth_d + relativedelta(months = 1) - relativedelta(seconds = 1)
                    self.intervals.append(
                        TimeInterval(self.intervals[-1].end + relativedelta(seconds = 1),
                                     end,
                                     '{}_{}_Week{}'.format(dir_id(), i, 's' if i > 1 else '')))
            else:
                ## every year, the birthday is special
                end = birth_d + relativedelta(years = y) + relativedelta(days = 1) - relativedelta(seconds = 1)
                self.intervals.append(
                    TimeInterval(self.intervals[-1].end + relativedelta(seconds = 1),
                                 end,
                                 '{}_{}_Birthday'.format(dir_id(), ordinal(y))))
            if y < 3:
                if y == 0:
                    months = range(1,12)
                else:
                    months = range(12*y, 12*y + 12)
                
                for i in months:
                    curr_dir += 1
                    end = birth_d + relativedelta(months = i + 1) - relativedelta(seconds = 1)
                    self.intervals.append(
                        TimeInterval(self.intervals[-1].end + relativedelta(seconds = 1),
                                     end,
                                     '{}_{}_Month{}'.format(dir_id(), i, 's' if i > 1 else '')))
            else:
                curr_dir += 1
                end = birth_d + relativedelta(years = y) - relativedelta(seconds = 1)
                self.intervals.append(
                    TimeInterval(self.intervals[-1].end + relativedelta(seconds = 1),
                                 end,
                                 '{}_{}_Years'.format(dir_id(), y)))
                   
    
    def find(self, dt):
        if dt < self.intervals[0].start:
            return None
        for interval in self.intervals:
            if interval.end >= dt:
                return interval        
        return None

    def get_date_tag(self, fn):
        with open(fn, 'rb') as fh:
            tags = exifread.process_file(fh, stop_tag="exifread DateTimeOriginal")
            dateTaken = tags["EXIF DateTimeOriginal"]
            return dateTaken
    
    def get_dt(self, fn):
        ext = os.path.splitext(fn)[1]
        if ext.upper() in ['.JPG', '.PNG']:
            try:
                tagval = self.get_date_tag(fn)
                return datetime.datetime.strptime(str(tagval), "%Y:%m:%d %H:%M:%S")                
            except Exception as err:
                logging.warning("Could not get taken date from image {}. Error was {}".format(fn, err))
        mtime = os.path.getmtime(fn)
        return datetime.datetime.fromtimestamp(mtime)
    
    def process_dir(self, d):
        for root, dirnames, filenames in os.walk(d):
            for filename in filenames:
                try:
                    mdt = self.get_dt(os.path.join(root, filename))
                    interval = self.find(mdt)
                    if not interval:
                        continue
                    yield filename, root, mdt, interval
                except Exception as err:
                    logging.warning("Could not process {} {}. Error was: {}".format(root, filename, err))
    
def main():
    parser = argparse.ArgumentParser(description = 'Process photo story of a person')
    parser.add_argument('--birth', '-b', help = 'Datetime of birth of the person, e.g. 1984-04-09 23:45:00', required = True)
    parser.add_argument('--output', '-o', help = 'Output directory', required = True)
    parser.add_argument('--input-dir', '-i', help = 'Input dir(s)', nargs = '*', required = True)
    parser.add_argument('--dry-run', '-d', help = 'Dry run', action = 'store_true')    

    args = parser.parse_args()

    birth_dt = datetime.datetime.strptime(args.birth, "%Y-%m-%d %H:%M:%S")
    # print args
    # print birth_dt
    intervals = Intervals(birth_dt)
    # pprint.pprint(intervals[:40])
    # return

    taken_names = set()

    file_count = 0
    total_size = 0
    
    for d in args.input_dir:
        for filename, root, mdt, interval in intervals.process_dir(d):
            src_fn = os.path.join(root, filename)                        
            ext = os.path.splitext(filename)[1]
            size = os.path.getsize(src_fn)
            if ext.upper() == ".MOV":
                if size < 5000000:
                    t = "Live"
                else:
                    t = "Movie"
            else:
                t = "Picture"
                continue

            new_dir = os.path.join(args.output, t, interval.name)
            new_fn = os.path.join(new_dir, datetime.datetime.strftime(mdt, "%Y%m%d_%H%M%S") + ext)            

            i = 0
            while new_fn in taken_names:
                new_fn = os.path.join(new_dir, datetime.datetime.strftime(mdt, "%Y%m%d_%H%M%S") + "_{}".format(i) + ext)
                i += 1

            if os.path.exists(new_fn):
                logging.debug("Same dt ext exists, skipping {} ...".format(new_fn))
                continue
                
            taken_names.add(new_fn)

            file_count += 1
            total_size += size
            if args.dry_run:
                logging.debug("Copying {} to {}".format(src_fn, new_fn))
            else:
                if not os.path.exists(new_dir):
                    os.makedirs(new_dir)            
                shutil.copyfile(src_fn, new_fn)
    logging.info("Copied {} files totalling {} bytes".format(file_count, total_size))
if __name__ == "__main__":
    main()
