import os
import sys
import errno
import pickle

from matplotlib import font_manager
from fontTools import ttLib
from PIL import Image, ImageFont, ImageDraw

from cvfont import CVFont, CVChar

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
        self.font_family = None
        self.font_subfamily = None
        self.successful_caches = None
        self.successful_caches_names = None
        self.unpickle_or_process()


    def unpickle_or_process(self):
        pkl_filename = os.path.join(self.cache_dir, FONTBANK_PICKLE_FILE)
        pkl_valid = False
        try:
            print "Attempting to load fontbank from pickle"
            pkl_file = open(pkl_filename, 'rb')
            (char_set,
             self.font_set,
             self.font_name,
             self.font_family,
             self.font_subfamily,
             self.successful_caches,
             self.successful_caches_names) = pickle.load(pkl_file)
            pkl_file.close()
            print "  Loaded fontbank from pickle!"
            if set(char_set) == set(self.char_set):
                pkl_valid = True
            else:
                print "  Pickled charset differs from current!"
        except:
            pass

        if not pkl_valid:
            print "Pickle FAIL... build data and cache it"
            self.build_fontbank()
            output = open(pkl_filename, 'wb')
            pickle.dump((self.char_set,
                         self.font_set,
                         self.font_name,
                         self.font_family,
                         self.font_subfamily,
                         self.successful_caches,
                         self.successful_caches_names), output, -1)
            output.close()
            print "Pickled fontbank for next time"

    def build_fontbank(self):
        # load fonts
        self.font_set = font_manager.findSystemFonts(fontpaths=None, fontext="ttf")
        self.successful_caches = {}
        self.successful_caches_names = {}

        # initialize directory, process fonts
        mkdir(self.cache_dir)
        self.font_name = {}
        self.font_family = {}
        self.font_subfamily = {}
        for f in self.font_set:
            data = self.fontInfo(f)
            self.font_name[f] = data[0]
            self.font_family[f] = data[1]
            self.font_subfamily[f] = data[2]

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

        # detect dupes
        if font_name in self.successful_caches_names:
            self.progress.advance(1, font_name + " was already processed from " + self.successful_caches_names[font_name])
            self.successful_caches[font] = False
            return

        mkdir(self.get_cache_dirname(font_name))

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

        if font not in self.successful_caches:
            self.successful_caches[font] = True
            self.successful_caches_names[font_name] = font


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


        # crop an image, centering the character based on bounding box, single-sized
        def char_center(img):
            # get bounding box (left, top, right, bottom) and determine width and height (wd/ht)
            bb = img.getbbox()
            if None is bb:
                raise BlankChar
            (bb_l, bb_t, bb_r, bb_b) = bb
            wd = bb_r - bb_l
            ht = bb_b - bb_t

            # contour generation will fail if the character touches the edge of the image,
            # so crop with a 1px border in mind.  so cropped image size = img_size - 2
            cis2 = self.img_size - 2
            if cis2 <= wd or cis2 <= ht:
                # crop aggressively, determine new bounds (nb)
                nb_l = bb_l - ((cis2 - wd) / 2)
                nb_t = bb_t - ((cis2 - ht) / 2)
                nb_r = nb_l + cis2
                nb_b = nb_t + cis2
                bb = (nb_l, nb_t, nb_r, nb_b)

            # crop to bounding box, then uncrop to center it
            img = img.crop(bb)
            (bb_l, bb_t, bb_r, bb_b) = bb
            wd = bb_r - bb_l
            ht = bb_b - bb_t

            # offsets will be negative
            nb_l = (wd - self.img_size) / 2
            nb_t = (ht - self.img_size) / 2
            nb_r = nb_l + self.img_size
            nb_b = nb_t + self.img_size

            img = img.crop((nb_l, nb_t, nb_r, nb_b))

            return img

        char_center(char_render()).save(filename)

    # get the typeface name and family names from the file
    def fontInfo(self, fontfile):
        FAMILY_ID = 1
        SUBFAMILY_ID = 2
        NAME_ID = 4
        PREFERRED_FAMILY_ID = 16

        def decoded(val):
            if '\000' in val:
                return unicode(val, 'utf-16-be').encode('utf-8')
            return unicode(val)

        font = ttLib.TTFont(fontfile)
        name = ""
        family = ""
        subfamily = ""
        preferred_family = ""
        for record in font['name'].names:
            if record.langID not in [0, 1033]: continue

            if record.nameID == NAME_ID and not name:
                name = decoded(record.string)
            elif record.nameID == FAMILY_ID and not family:
                family = decoded(record.string)
            elif record.nameID == SUBFAMILY_ID and not subfamily:
                subfamily = decoded(record.string)
            elif record.nameID == PREFERRED_FAMILY_ID and not preferred_family:
                preferred_family = decoded(record.string)

        # some fonts apparently have wrong names in field 1 and correct names in field 16
        return name, (preferred_family if preferred_family else family), subfamily


    # build filename for specific font/char
    def get_cache_dirname(self, font_name):
        relative = os.path.join(self.cache_dir, font_name)
        absolute = os.path.join(os.getcwd(), relative)
        return absolute

    # build filename for specific font/char
    def get_cache_filename(self, font_name, char):
        thefile = str(self.img_size) + "_" + char + "." + CHAR_IMG_EXT
        return os.path.join(self.get_cache_dirname(font_name), thefile)

    # get a CVFont object (cache-backed)
    def get_font(self, font_name):
        return CVFont(self.char_set, font_name, self.get_cache_filename)

    # get a CVChar object (cache-backed)
    def get_char(self, font_name, char):
        filename = self.get_cache_filename(font_name, char)
        return CVChar(font_name, char, filename)
