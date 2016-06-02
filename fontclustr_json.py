from progress import DiscreteProgress
from fontbank import FontBank
import string
import itertools
import json

FONT_CACHE_DIR = "cache"
CHAR_IMG_SIZE = 200
JSON_OUTPUT_FILE = "report/distance_information.json"

def mkCharSet():
    uc = string.uppercase
    lc = string.lowercase
    ret = ""
    for i, c in enumerate(uc):
        ret = ret + c + lc[i]

    #return "AaBbCc"
    #return ret + "1234567890" # "AaBbCc"
    return "AaBbCcGgHhKkOoPpTtXx"

charset = mkCharSet()
fb = FontBank(FONT_CACHE_DIR, CHAR_IMG_SIZE, charset, DiscreteProgress(0.1))

valid_fonts = []
for f in fb.font_set:
    name = fb.font_name[f]
    font = fb.get_font(name)
    if fb.successful_caches[f]:
        if font.is_null():
            print "is null font:", name
        else:
            valid_fonts.append(f)

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
with open(JSON_OUTPUT_FILE, "w") as outfile:
    json.dump({
        "charset": charset,
        "fonts": [{
            "name": fb.font_name[f],
            "family": fb.font_family[f],
            "subfamily": fb.font_subfamily[f]
               } for f in valid_fonts],
        "distances": distances
    }, outfile)
