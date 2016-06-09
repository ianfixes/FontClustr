import cv2

class CVFont(object):
    def __init__(self, charset, fontname, get_cache_fn):
        self.charset = charset
        self.fontname = fontname
        self.chars = {}
        for c in self.charset:
            filename = get_cache_fn(fontname, c)
            self.chars[c] = CVChar(fontname, c, filename)

    def distance_from(self, another_cv_font):
        dist = 0
        for c in self.charset:
            dist = dist + self.chars[c].contour_distance_from(another_cv_font.chars[c])
        return dist

    def is_null(self):
        (_, c0) = self.chars.items()[0]
        for _, c in self.chars.items()[1:]:
            if 0 < c0.contour_distance_from(c):
                return False
        return True



class CVChar(object):
    def __init__(self, fontname, charname, filename):
        self.c = charname
        self.fontname = fontname
        self.filename = filename

        self.img = None
        self.edg = None
        self.sto = None
        self.cnt = None
        self.tre = None

    def contour_distance_from(self, another_cv_char,
                              method = cv2.cv.CV_CONTOURS_MATCH_I2):
        #method can also be cv2.cv.CV_CONTOURS_MATCH_I1 or I3
        self.make_contour()
        another_cv_char.make_contour()
        return cv2.matchShapes(self.cnt, another_cv_char.cnt, method, 0)

    def vassert(self, expr):
        if not expr:
            print "About to fail on", self.filename
        assert(expr)

    def make_contour(self):
        if self.cnt is not None:
            return

        self.img = cv2.imread(str(self.filename), cv2.IMREAD_GRAYSCALE)

        self.vassert(self.img is not None)
        self.vassert(self.img.data)

        contours, hierarchy = cv2.findContours(self.img, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        self.cnt = contours[-1]

        self.vassert(self.cnt is not None)
        self.vassert(len(self.cnt))

        del self.img
        self.img = None
        return
