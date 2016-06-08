from progress import DiscreteProgress
from fontbank import FontBank
import string
import json
import os

JSON_OUTPUT_BASE_DIR = "report"
JSON_OUTPUT_BASE_NAME = "distance_information_"
KEY_FONTS = "fonts"
KEY_DISTANCES = "distances"

# handles the caching and calculation of "distances" between fonts
class DistanceBank(object):

    def __init__(self, img_cache_dir, img_size):
        self.img_cache_dir = img_cache_dir
        self.img_size = img_size

    # embed char set into filename
    def get_filename(self, charset):
        return os.path.join(JSON_OUTPUT_BASE_DIR, JSON_OUTPUT_BASE_NAME + charset + ".json")

    # get a font info list, and a matrix of distances between fonts (aligned indexes)
    # this is an expensive thing to calculate.
    # so, make sure results are cached and return them
    def get_distances(self, charset):
        fonts = None
        distances = None
        try:
            with open(self.get_filename(charset)) as f:
                data = json.load(f)
                fonts = data.get(KEY_FONTS, None)
                distances = data.get(KEY_DISTANCES, None)
        except Exception as e:
            print "DistanceBank.get_distances error:", e

        if fonts is None or distances is None:
            fonts, distances = self.cache_distances(charset)

        return fonts, distances

    # pull valid fonts (the non-null fonts) from a font bank
    def get_valid_fonts(self, font_bank):
        valid_fonts = []
        for f in font_bank.font_set:
            name = font_bank.font_name[f]
            font = font_bank.get_font(name)
            if font_bank.successful_caches[f]:
                if font.is_null():
                    print "is null font:", name
                else:
                    valid_fonts.append(f)
        return valid_fonts

    # construct a 2d array of font distances, aligned keys with valid_fonts
    def get_font_distances(self, valid_fonts, font_bank):
        fb = font_bank

        # font distance matrix
        distances = [[(0 if i == j else None) for i, __ in enumerate(valid_fonts)] for j, _ in enumerate(valid_fonts)]
        print distances
        prog = DiscreteProgress(0.0001)
        n = len(valid_fonts)
        prog.begin_task("comparing", (n * (n - 1)) / 2, "Comparing distances between %d fonts" % n)
        for i in range(len(valid_fonts)):
            a = valid_fonts[i]
            name_a = fb.font_name[a]
            print name_a
            for j in range(i + 1, len(valid_fonts)):
                b = valid_fonts[j]
                name_b = fb.font_name[b]
                #print name_a, "vs", name_b
                dist = fb.get_font(name_a).distance_from(fb.get_font(name_b))
                prog.advance(1)
                distances[i][j] = dist
                distances[j][i] = dist

        prog.end_task("Completed successfully")
        return distances

    # calculate and cache distances pulled from a font bank
    def cache_distances(self, charset):
        fb = FontBank(self.img_cache_dir, self.img_size, charset, DiscreteProgress(0.1))

        valid_fonts = self.get_valid_fonts(fb)
        distances = self.get_font_distances(valid_fonts, fb)

        # cache the results
        out_fonts = [{
            "name": fb.font_name[f],
            "family": fb.font_family[f],
            "subfamily": fb.font_subfamily[f]
        } for f in valid_fonts]

        with open(self.get_filename(charset), "w") as outfile:
            json.dump({
                "charset": charset,
                KEY_FONTS: out_fonts,
                KEY_DISTANCES: distances
            }, outfile)

        return out_fonts, distances
