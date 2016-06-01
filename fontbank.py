import os
import sys
import errno
import pickle

from matplotlib import font_manager
from fontTools import ttLib
from progress import DiscreteProgress
from PIL import Image, ImageFont, ImageDraw

# makes a directory even if it's already there
def mkdir(path):
    try:
        os.mkdir(path)
    except OSError, err:
        if err.errno != errno.EEXIST:
            raise

FONTBANK_PICKLE_FILE = "fontbank.pkl"
CHAR_IMG_EXT = "png"

# If a character renders to a blank image
class BlankChar(Exception):
    pass

# If a character doesn't render (e.g. Apple Emoji: only certain pixel sizes allowed)
class InvalidRender(Exception):
    pass


# FontClustr works on a set of typefaces, and compares them using a set of characters.
# These operations are backed by a set of images cached on disk.
# This class manages the repositiory of cache-backed typeface objects
class FontBank(object):
    def __init__(self, cache_dir, img_size, char_set, progress):
        # private vars
        self.cache_dir = cache_dir
        self.img_size = img_size
        self.char_set = char_set
        self.progress = progress

        # computed stuff
        self.font_set = None
        self.font_name = None
        self.successful_caches = None
        self.unpickle_or_process()


    def unpickle_or_process(self):
        pkl_filename = os.path.join(self.cache_dir, FONTBANK_PICKLE_FILE)
        try:
            print "Attempting to load fontbank from pickle"
            pkl_file = open(pkl_filename, 'rb')
            (self.font_set, self.font_name, self.successful_caches) = pickle.load(pkl_file)
            pkl_file.close()
            print "  Loaded fontbank from pickle!"
        except:
            print "Pickle FAIL... build data and cache it"
            self.build_fontbank()
            output = open(pkl_filename, 'wb')
            pickle.dump((self.font_set, self.font_name, self.successful_caches), output, -1)
            output.close()
            print "Pickled fontbank for next time"

    def build_fontbank(self):
        # load fonts
        self.font_set = font_manager.findSystemFonts(fontpaths=None, fontext="ttf")
        self.successful_caches = {}

        # initialize directory, process fonts
        mkdir(self.cache_dir)
        self.font_name = dict([(f, self.realFontName(f)) for f in self.font_set])
        self.cache_all_fonts()


    # Cache all fonts, and mark as cached
    def cache_all_fonts(self):
        steps = len(self.font_set) * len(self.char_set)
        self.progress.begin_task("cacheing", steps, "Caching %d characters (%d fonts)" % (steps, len(self.font_set)))

        for font in self.font_set:
            self.cache_one_font(font)

        num_successful = self.successful_caches.values().count(True)
        self.progress.end_task("Successfully cached %d of %d fonts" % (num_successful, len(self.font_set)))


    # Cache all characters of one font
    def cache_one_font(self, font):
        font_name = self.font_name[font]
        mkdir(self.get_cache_dirname(font_name))

        self.successful_caches[font] = True
        for char in self.char_set:
            try:
                self.cache_one_char(font, char)
            except KeyboardInterrupt:
                raise
            except InvalidRender:
                self.progress.advance(1, font_name + " character " + char + " can't render at this size")
                self.successful_caches[font] = False
            except BlankChar:
                self.progress.advance(1, font_name + " character " + char + " renders blank")
                self.successful_caches[font] = False
            except:
                self.progress.advance(1, "err on " + font_name + " was " + str(sys.exc_info()[0]))
                self.successful_caches[font] = False
            else:
                self.progress.advance(1)


    # Cache one of something
    def cache_one_char(self, font_file, char):
        font_name = self.font_name[font_file]
        filename = self.get_cache_filename(font_name, char)

        if os.path.exists(filename): return

        #create a white-on-black image of a character in the given font, double-sized
        def char_render():
            image = Image.new("1", (self.img_size, self.img_size), 0)
            try:
                usr_font = ImageFont.truetype(font_file, self.img_size / 2)
            except:
                raise InvalidRender()
            d_usr = ImageDraw.Draw(image)
            d_usr.fontmode = "1" # this apparently sets (anti)aliasing.
            d_usr.text((0, 0), char, 1, font=usr_font)

            return image


        #crop an image, centering the character based on bounding box, single-sized
        def char_center(img):
            #get bounding box (left, top, right, bottom) and determine width and height (wd/ht)
            bb = img.getbbox()
            if None is bb:
                raise BlankChar
            (bb_l, bb_t, bb_r, bb_b) = bb
            wd = bb_r - bb_l
            ht = bb_b - bb_t


            if self.img_size <= wd or self.img_size <= ht:
                #crop aggressively: imgsize minus a 1px border. calc new bounds
                cis2 = self.img_size - 2
                nb_l = bb_l - ((cis2 - wd) / 2)
                nb_t = bb_t - ((cis2 - ht) / 2)
                nb_r = nb_l + cis2
                nb_b = nb_t + cis2
                bb = (nb_l, nb_t, nb_r, nb_b)

            img = img.crop(bb)

            #now un-crop, to center it
            (bb_l, bb_t, bb_r, bb_b) = bb
            wd = bb_r - bb_l
            ht = bb_b - bb_t

            #offsets will be negative
            nb_l = (wd - self.img_size) / 2
            nb_t = (ht - self.img_size) / 2
            nb_r = nb_l + self.img_size
            nb_b = nb_t + self.img_size

            img = img.crop((nb_l, nb_t, nb_r, nb_b))

            return img

        char_center(char_render()).save(filename)


    def realFontName(self, fontfile):
        FONT_SPECIFIER_NAME_ID = 4
        FONT_SPECIFIER_FAMILY_ID = 1

        # http://starrhorne.com/posts/font_name_from_ttf_file/
        def shortName(font):
            """Get the short name from the font's names table"""
            name = ""
            family = ""
            for record in font['name'].names:
                if record.nameID == FONT_SPECIFIER_NAME_ID and not name:
                    if '\000' in record.string:
                        name = unicode(record.string, 'utf-16-be').encode('utf-8')
                    else:
                        name = record.string
                elif record.nameID == FONT_SPECIFIER_FAMILY_ID and not family:
                    if '\000' in record.string:
                        family = unicode(record.string, 'utf-16-be').encode('utf-8')
                    else:
                        family = record.string
                if name and family:
                    break
            return name, family

        return unicode(shortName(ttLib.TTFont(fontfile))[1])



    #build filename for specific font/char
    def get_cache_dirname(self, font_name):
        relative = os.path.join(self.cache_dir, font_name)
        absolute = os.path.join(os.getcwd(), relative)
        return absolute

    #build filename for specific font/char
    def get_cache_filename(self, font_name, char):
        thefile = str(self.img_size) + "_" + char + "." + CHAR_IMG_EXT
        return os.path.join(self.get_cache_dirname(font_name), thefile)
