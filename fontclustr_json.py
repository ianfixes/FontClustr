from progress import DiscreteProgress
from fontbank import FontBank
from distancebank import DistanceBank
import string
import itertools
import json

FONT_CACHE_DIR = "cache"
CHAR_IMG_SIZE = 200

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

db = DistanceBank(FONT_CACHE_DIR, CHAR_IMG_SIZE)
fonts, distances = db.get_distances(charset)
print fonts
print distances
