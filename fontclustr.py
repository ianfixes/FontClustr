#!/usr/bin/env python

#/*************************************************************************
#
#    fontclustr.py: a program that clusters fonts based on their appearance
#    
#    Copyright (C) 2010 Ian Katz
#
#    This software was written by Ian Katz
#    contact: ifreecarve@gmail.com
#
#    This file is part of FontClustr.
#
#    FontClustr is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    FontClustr is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with FontClustr.  If not, see <http://www.gnu.org/licenses/>.
#
#*************************************************************************/


import os
import sys
import time
import PythonMagick
import gd
import errno
import math
import pygame
import string
import numpy
import pickle

from opencv import cv
from opencv import highgui
from fontTools import ttLib

import tree


#makes a pleasing set of characters
def mkCharSet():
    uc = string.uppercase
    lc = string.lowercase
    ret = ""
    for i, c in enumerate(uc):
        ret = ret + c + lc[i]
        
    return ret + "1234567890" # "AaBbCc"

#for the realFontName function
FONT_SPECIFIER_NAME_ID = 4
FONT_SPECIFIER_FAMILY_ID = 1

FONT_CACHE_DIR = "cache"
CHAR_IMG_SIZE = 100
SAFETY_MARGIN = 0.85
CHAR_SET = mkCharSet()
CHAR_IMG_EXT = ".bmp"
PROCESS_CACHE_FILE = FONT_CACHE_DIR + os.path.sep + "4_hours_worth_of_data.pkl"
TREE_CACHE_FILE = FONT_CACHE_DIR + os.path.sep + "master_tree.pkl"

#makes a directory even if it's already there
def mkdir(path):
    try:
        os.mkdir(path)
    except OSError, err:
        if err.errno != errno.EEXIST:
            raise

"""
#display an image for the user
def viewFile(filename):
    img = PythonMagic.Image(filename)
    img.display()


highgui.cvStartWindowThread()

def viewCV(img):
    name = "win" + time.ctime()
    highgui.cvNamedWindow(name)
    highgui.cvShowImage(name, img)
    highgui.cvWaitKey(0)
"""

def fontDistance(font1, font2):
    dist = 0
    for c in CHAR_SET:
        dist = dist + charDistance(charFile(font1, c), charFile(font2, c))

    return dist

#if all the font characters are the same (probably boxes) the font is useless
def isNullFont(fontname):
    c0 = CHAR_SET[0]
    for c in CHAR_SET[1:50]:
        if 0 < charDistance(charFile(fontname, c0), charFile(fontname, c)):
            return False
    print fontname, "seems null"
    return True
                                 

#contour tree matching cost between 2 characters
def charDistance(file1, file2, doLogPolar = False):       
    #have to keep these around to prevent segfaults when storage drops out of scope
    img = {}
    edg = {}
    sto = {}
    cnt = {}
    tre = {}
    
    #poor result
    """
    return cv.cvMatchShapes(
        highgui.cvLoadImage(file1, highgui.CV_LOAD_IMAGE_GRAYSCALE),
        highgui.cvLoadImage(file2, highgui.CV_LOAD_IMAGE_GRAYSCALE),
        #cv.CV_CONTOURS_MATCH_I1,
        #cv.CV_CONTOURS_MATCH_I2,
        cv.CV_CONTOURS_MATCH_I3,
        0,
        )
        """

    #get files
    def getContour(somefile):
        #print somefile
        somefile = str(somefile)

        # doesn't seem to produce improvement... actually, i think it hurts 
        def toLogPolar(img):
            scale = CHAR_IMG_SIZE / math.log(CHAR_IMG_SIZE)

            #convert to color, else logpolar crashes
            clr = cv.cvCreateImage(cv.cvSize(CHAR_IMG_SIZE, CHAR_IMG_SIZE), 8, 3);
            cv.cvCvtColor(img, clr, cv.CV_GRAY2RGB)
            
            dst = cv.cvCreateImage(cv.cvSize(CHAR_IMG_SIZE, CHAR_IMG_SIZE), 8, 3);
            cv.cvLogPolar(clr, dst, 
                          cv.cvPoint2D32f(CHAR_IMG_SIZE / 2, CHAR_IMG_SIZE / 2), 
                          scale, cv.CV_WARP_FILL_OUTLIERS)

            #convert to grayscale
            gry = cv.cvCreateImage(cv.cvGetSize(dst), 8, 1);
            cv.cvCvtColor(dst, gry, cv.CV_RGB2GRAY)
            return gry

        img[somefile] = highgui.cvLoadImage(somefile, highgui.CV_LOAD_IMAGE_GRAYSCALE)
        if doLogPolar:
            img[somefile] = toLogPolar(img[somefile])

        #image is already white on black, so i guess we dont need this
        edg[somefile] = cv.cvCreateImage(cv.cvGetSize(img[somefile]), 8, 1)
        cv.cvThreshold(img[somefile], edg[somefile], 1, 255, cv.CV_THRESH_BINARY)

        sto[somefile] = cv.cvCreateMemStorage (0)
        nb_contours, cnt[somefile] = cv.cvFindContours (img[somefile], #edg[somefile],
                                                        sto[somefile],
                                                        cv.sizeof_CvContour,
                                                        cv.CV_RETR_TREE,
                                                        cv.CV_CHAIN_APPROX_NONE,
                                                        cv.cvPoint (0,0))
        #tre[somefile] = cv.cvCreateContourTree(cnt[somefile], sto[somefile], 0)
        
        return

    #make a tree... shorthand func
    def makeTree(id):
        tre[id] = cv.cvCreateContourTree(cnt[id], sto[id], 0)
    

    getContour(file1)
    getContour(file2)

    return cv.cvMatchShapes(
        cnt[file1],
        cnt[file2],
        #cv.CV_CONTOURS_MATCH_I1,
        cv.CV_CONTOURS_MATCH_I2, #seems to work best in my hokey example
        #cv.CV_CONTOURS_MATCH_I3,
        0,
        )


    # this method may be better, but causes a lot of crashes in the openCV library...
    """
    makeTree(file1)
    makeTree(file2)
    print "cvMatchContourTrees"
    return cv.cvMatchContourTrees(tre[file1], tre[file2], 1, 0)
    """



#build filename for specific font/char
def charFile(fontname, charname):
    return FONT_CACHE_DIR + os.path.sep + fontname + os.path.sep + charname + CHAR_IMG_EXT


def cacheFonts(allfonts):    

    #create a white-on-black image of a character in the given font, save to given filename
    def renderChar(font, c, outname):
        surface = pygame.Surface ((CHAR_IMG_SIZE * 2, CHAR_IMG_SIZE * 2), depth=8)
        surface.fill ((0, 0, 0))
        
        sf = font.render (c, False, (255, 255, 255))
        surface.blit (sf, (CHAR_IMG_SIZE * 0.5, CHAR_IMG_SIZE * 0.5))
        
        pygame.image.save(surface, outname)


    #crop an image, centering the character based on bounding box
    def centerChar(outname):
        outname = str(outname)
        img = PythonMagick.Image(outname)
    
        bb = img.boundingBox()
    
        newbb = PythonMagick._PythonMagick.Geometry(
            CHAR_IMG_SIZE, 
            CHAR_IMG_SIZE, 
            bb.xOff() - ((CHAR_IMG_SIZE - bb.width()) / 2),
            bb.yOff() - ((CHAR_IMG_SIZE - bb.height()) / 2),
            )
    
        img.crop(newbb)
        img.write(outname)

    outfonts = []

    #go through fonts and generate/save each char
    mkdir(FONT_CACHE_DIR)
    totalfonts = len(allfonts)
    processedfonts = 0.0
    for fontname in allfonts:
        percentdone = "[%02.0f%%]" % math.floor(processedfonts / totalfonts * 100)
        processedfonts = processedfonts + 1

        fontdir = FONT_CACHE_DIR + os.path.sep + fontname

        if os.path.exists(fontdir + "/done"): 
            #print "skipping", percentdone, fontname
            outfonts.append(fontname)
            continue
        
        print "cacheing", percentdone, fontname

        try:
            mkdir(fontdir)
            font = pygame.font.Font(pygame.font.match_font(fontname), 
                                    int(math.floor(CHAR_IMG_SIZE * SAFETY_MARGIN))
                                    )

            #make the images
            for i, c in enumerate (CHAR_SET):
                outname = fontdir + os.path.sep + c + CHAR_IMG_EXT
                renderChar(font, c, outname)

            #trim the images
            for i, c in enumerate (CHAR_SET):
                outname = fontdir + os.path.sep + c + CHAR_IMG_EXT
                centerChar(outname)

            mkdir(fontdir + "/done")

        except KeyboardInterrupt:
            raise
        except:
            print "               --- oops! ignoring.  err was", sys.exc_info()[0]
        else:
            outfonts.append(fontname)



    print "processing 100%  done after", int(processedfonts), "fonts"

    return outfonts


# turn pygame's "arialblack" into "Arial Black" so browsers can use it
def realFontName(afont):

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

    fontfile = pygame.font.match_font(afont)
    try:
        return unicode(shortName(ttLib.TTFont(fontfile))[1]) #seems to work better
        #return shortName(ttLib.TTFont(fontfile))[0]
    except:
        return unicode(afont)


#get the 2 fonts with the smallest distance between them
def getMinFontDistance(amatrix):
    mindist = 1000000
    minfonts = (-1,-1)
    size = len(amatrix)
    for i in range(size):
        for j in range(i, size):
            if i == j: continue
            newdist = amatrix[i][j]
            #if newdist > 0 and mindist > newdist:
            if mindist > newdist:
                mindist = newdist
                minfonts = (i, j)

    #note that j < i in all cases
    return minfonts

#compute all the distances
def makeFontMatrix(font_list):
    numfonts = len(font_list)
    #initialize matrix
    matrix = [[0 for col in range(numfonts)] for row in range(numfonts)]
    #matrix = [[0 for col in range(0, row)] for row in range(len(font_list))]

    totalwork = (numfonts ** 2. + numfonts) / 2
    donework = 0
    #we could do this during init if we handled symmetry better during reduction
    for i, font in enumerate(font_list):
        for j in range(i, len(font_list)):
            if i == j:
                matrix[i][j] = 0
            else:
                #print font_list[i], ":: font_list.remove(\"" + font_list[j] + "\")"
                f1 = font_list[i]
                f2 = font_list[j]
                distance = fontDistance(f1, f2)
                donework = donework + 1
                done = "[%02.2f%%] %d" % ((math.floor(donework / totalwork * 10000) / 100), numfonts - i)
                print done, "\t", distance, "\t", f1, "::", f2
                matrix[i][j] = distance
                matrix[j][i] = distance

    return matrix


#remove any all-zero rows in a matrix
def deZeroify(font_list, font_matrix):
    i = len(font_list)
    while i > 0:
        i = i - 1 
        if all(map(lambda x: x == 0, font_matrix[i])):
            print "Removing all-zero-distance", font_list[i]
            font_list = font_list[:i] + font_list[i+1:]
            font_matrix = font_matrix[:i] + font_matrix[i+1:]
            for j, r2 in enumerate(font_matrix):
                font_matrix[j] = r2[:i] + r2[i+1:]

    return (font_list, font_matrix)


#remove any fonts that don't have corresponding files
def deMissingfontify(font_list, font_matrix):
    i = len(font_list)
    while i > 0:
        i = i - 1 
        if None is pygame.font.match_font(font_list[i]):
            print "Removing font-with-no-ttf-file", font_list[i]
            font_list = font_list[:i] + font_list[i+1:]
            font_matrix = font_matrix[:i] + font_matrix[i+1:]
            for j, r2 in enumerate(font_matrix):
                font_matrix[j] = r2[:i] + r2[i+1:]

    return (font_list, font_matrix)


# where the magic happens
def makeFontTree(font_list, matrix):

    #initialize tree(s) for the shittiest agglomerative clustering algo ever written
    # (but in fairness, i ONLY have distances to work with -- not dimensions)
    trees = []
    for i, font in enumerate(font_list):
        l = tree.leaf()
        l.ptr = i
        trees.append(l)

    # find pairs of fonts in the matrix and cluster them until we have 1 tree left
    while 1 < len(trees):
        print "merges remaining", len(trees) - 1

        # find min font
        (f1, f2) = getMinFontDistance(matrix)
        if (-1, -1) == (f1, f2):
            print matrix

        #iterate through the other trees
        new_trees = []
        for i, t in enumerate(trees):
            if i == f1 or i == f2: continue
            new_trees.append(t)

        new_matrix = []
        #iterate through the rest of the matrix and add those rows here
        for i, r in enumerate(matrix):
            if i == f1 or i == f2: continue
            new_row = []
            for j, c in enumerate(matrix[i]):
                if j == f1 or j == f2: continue
                new_row.append(c)
            new_matrix.append(new_row)
        

        # create new branch
        t1 = trees[f1]
        t2 = trees[f2]
        br = tree.branch()
        br.set_branches(t1, t2)

        # add as last tree
        new_trees.append(br)


        #this code uses weighted averages to reconcile distances, 
        # ... but doesn't produce great results
        """
        # calculate new row... last in the matrix, so the last row is 0
        new_row = []
        weight_t1 = t1.num_leaves()
        weight_t2 = t2.num_leaves()
        weight = weight_t1 + weight_t2
        for i, dist in enumerate(matrix[f1]):
            if i == f1 or i == f2: continue

            #is averaging a bad idea?  what about assuming a worst-case scenario?
            # i guess that would mean a huge pythagorean calculation... maybe later
            s1 = matrix[f1][i] * weight_t1
            s2 = matrix[f2][i] * weight_t2            avg_dist = (s1 + s2) / weight
            new_row.append(avg_dist)
            """

        # calculate new row... pythagorean distance
        new_row = []
        for i, dist in enumerate(matrix[f1]):
            if i == f1 or i == f2: continue

            s1 = matrix[f1][i]
            s2 = matrix[f2][i]
            pythag_dist = math.sqrt(s1**2 + s2**2)

            new_row.append(pythag_dist)


        new_row.append(0) #this is the last row, distance to self = 0
        new_matrix.append(new_row)



        #complete the last col of the matrix from the last row
        mylen = len(matrix[0])
        for i, dontcare in enumerate(new_matrix):
            if i < mylen - 2:
                new_matrix[i].append(new_row[i])

        #update vars
        trees = new_trees
        matrix = new_matrix

        #repeat until there is 1 left

    return trees[0]

def makeHtmlHeader(title, depth = 2, moreheader = ""):
    stylepath = ("../" * depth) + "style.css"
    html = "<html>\n<head>\n <title>" + title + "</title>"
    html = html + "\n <meta http-equiv='content-type' content='text/html; charset=UTF-8' />"
    html = html + "\n <link rel='stylesheet' type='text/css' href='" + stylepath + "' />"
    html = html + "\n" + moreheader
    html = html + "\n </head>\n<body>"
    return html

def makeFontClustrHeader():
    return """<html xmlns="http://www.w3.org/1999/xhtml">
<head>
 <title>FontClustr - A Better Way To Choose Fonts, by Ian Katz</title>
 <meta http-equiv='content-type' content='text/html; charset=UTF-8' />
 <link rel='stylesheet' type='text/css' href='style.css' />
 <link rel='stylesheet' type='text/css' href='tabber.css' />

 <script type="text/javascript" src="tabber.js"></script>

 <script type="text/javascript">
  <!--
function getElementsByClassName(classname, node) {
    if (!node) node = document.getElementsByTagName("body")[0];
    var a = [];
    var re = new RegExp('\\\\b' + classname + '\\\\b');
    var els = node.getElementsByTagName("*");
    for (var i = 0, j = els.length; i < j; i++)
        if (re.test(els[i].className))
            a.push(els[i]);
    return a;
}

function updateText() {
    newtext = document.getElementById('newtext').value;
    newsize = document.getElementById('newsize').value;
    newfg = document.getElementById('newfgcolor').value;
    newbg = document.getElementById('newbgcolor').value;


    var fonts = getElementsByClassName("font_text");
    for (var i = 0, j = fonts.length; i < j; i++)
    {
        f = fonts[i];
        f.style.color = "#" + newfg;
        f.style.fontSize = newsize;
        f.innerHTML = newtext;
    }

    var uls = document.getElementsByTagName("ul");
    for (var i = 0, j = uls.length; i < j; i++)
    {
        u = uls[i];
        u.style.color = "#" + newfg;
    }
    
    var fonts = getElementsByClassName("font_entry");
    for (var i = 0, j = fonts.length; i < j; i++)
    {
        f = fonts[i];
        f.style.color = "#" + newfg;
    }
    document.getElementsByTagName("body")[0].style.backgroundColor = "#" + newbg;
}
 -->
</script>

 </head>
<body>
<div class="tabber" id="tab1">

  <div class="tabbertab">
    <h2>FontClustr</h2>
    <p style='width:50em;'><a href="http://tinylittlelife.org/?cat=16">FontClustr</a> was written by <a href="http://www.linkedin.com/in/ikatz">Ian Katz</a> in 2010.  Hopefully it will be obsolete (incorporated
       into mainstream font-selection widgets) by 2011!
    </p>
  </div>

  <div class="tabbertab">
    <h2><a name="tab1">Text Attributes</a></h2>
    <table class="text_attributes">
     <tr>
      <th>Sample Text</th>
      <td><input type='text' id='newtext' value='AaBbCcDdEe' style='width:30em;' /></td>
     </tr>
     <tr>
      <th>Font Size</th>
      <td><input type='text' id='newsize' value='100px' style='width:10em;' /></td>
     </tr>
     <tr>
      <th>Background Color #</th>
      <td><input type='text' id='newbgcolor' value='000000' class='color' maxlength="6" /></td>
     </tr>
     <tr>
      <th>Text Color #</th>
      <td><input type='text' id='newfgcolor' value='FFFFFF' class='color' maxlength="6" /></td>
     </tr>
    </table>  
    <input type='button' onClick='updateText();' value='Apply' style='float:right;'/>
    <br style="clear:both;" />
  </div>

  <div class="tabbertab">
    <h2>Thanks</h2>
   The following software projects made FontClustr possible:
   <ul>
    <li><a href="http://opencv.willowgarage.com/wiki/">OpenCV</a></li>
    <li><a href="http://www.pygame.org">PyGame</a></li>
    <li><a href="http://www.imagemagick.org">PythonMagick</a></li>
    <li><a href="http://sourceforge.net/projects/fonttools/">TTX/FontTools</a></li>
    <li><a href="http://www.barelyfitz.com/projects/tabber/">Tabber</a></li>
   </ul>
  </div>

  <div class="tabbertab" id="hideit">
    <h2>Hide</h2>
  </div>

</div>
"""

# make 1 page per font, listing the nearest and furthest fonts
def makeFontWebPages(font_list, font_matrix):

    def makeEntry(fontname):
        def img(c):
            #fixme... see if i need a title with the font name
            return "<img src='../" + fontname + "/" + c + CHAR_IMG_EXT + "' alt='" + c + "' />"

        ret = "<div class='font_entry'><a href='../" + fontname + "/index.html'>"
        for c in CHAR_SET[:10]:
            ret = ret + img(c)
        ret = ret + "</a>" + fontname + "</div>"
        return ret

    def makeSection(fonts, title):
        if 0 == len(fonts): return ""
        ret = "\n<h2>" + title + "</h2>"
        for f in fonts:
            ret = ret + makeEntry(font_list[f])
        return ret
        

    #iterate through matrix

    def makePage(index, fontname):
        print "making webpage for", fontname
        min_similar_fonts = 5
        max_similar_fonts = 20
        row = []
        fonts_near = []
        fonts_far  = []
        fonts_zero = []

        
        #build out a webpage
        html = makeHtmlHeader("FontClustr - " + fontname)
        html = html + "\n<h1>" + fontname + "</h1>"
        html = html + "\n<div class='nav'>"
        if index > 0:
            prevfont = font_list[index - 1]
            html = html + "<a href='../" + prevfont + "/index.html'>&laquo; " + prevfont + "</a>"
        html = html + "<a href='../index.html'>Index</a>"
        if index < (len(font_list) - 1):
            nextfont = font_list[index + 1]
            html = html + "<a href='../" + nextfont + "/index.html'>" + nextfont + " &raquo;</a>"
        html = html + "</div>"
        html = html + makeEntry(fontname)


        #convert into list of font_list indices, sorted by ascending distance
        # pull out 0's into a section for 0's
        d = {}
        for i, v in enumerate(font_matrix[index]):
            if index == i: continue # we don't want the self-referencing distance
            if all(map(lambda x: x == 0, font_matrix[i])):
                fonts_zero.append(i)
            else:
                d[i] = v

        index_and_val = sorted(d.items(), lambda x, y: cmp(x[1], y[1]))
    
        #bomb out if the font sucks
        if 0 == len(index_and_val): 
            html = html + "<h2>This font broke the distance calculation algorithm (all distances 0).</h2>"
        else:

            # run statistics on the rest
            stddev = numpy.std(dict(index_and_val).values())

            # window_size = 1 std deviation
            (i, v) = index_and_val[0]
            max_of_mins = v + stddev

            n = 0
            for (i, v) in index_and_val:
                if 0 < v: n = n + 1
                if n <= min_similar_fonts or v < max_of_mins:
                    if n >= max_similar_fonts - 1: break
                    fonts_near.append(i)

            # get the 5 max distance fonts
            fonts_far = dict(index_and_val[-5:]).keys()

            html = html + makeSection(fonts_near, "Closest Fonts")
            html = html + makeSection(fonts_far, "Furthest Fonts")
            html = html + makeSection(fonts_zero, "Zero-distance Fonts (errors?)")

        html = html + "\n</body></html>"
        #save it
        f = open(FONT_CACHE_DIR + "/" + fontname + "/index.html", 'w')
        f.write(html)
        f.close()

        return

    for i, f in enumerate(font_list):
        makePage(i, f)

    #make index page
    mainindex = open(FONT_CACHE_DIR + "/index.html", 'w')
    mainindex.write(makeHtmlHeader("FontClustr - Ian's Font Clustering App (output index)", 1))
    mainindex.write("<h1>Fonts Processed</h1><ul>")
    for i, f in enumerate(font_list):
        mainindex.write("\n <li><a href='" + f + "/index.html'>" + f + "</a></li>")
        
    mainindex.write("</ul></body></html>")
    mainindex.close()
                        

####################################
          
pygame.init ()
allfonts = pygame.font.get_fonts()


#stupid hack.
# without these lines, something in opencv segfaults during distance calculation
# it's probably because the elegante font is huge and goes off the edge of the bitmap
# so it can and probably should be fixed.
if "elegante" in allfonts: allfonts.remove("elegante")

allfonts.sort()

print "\nIt's GO TIME\n"

goodfonts = cacheFonts(allfonts)

print "\nAfter caching,", len(goodfonts), "of", len(allfonts), "fonts remain\n"

allfonts = goodfonts

try:
    print "Attempting to load data from cache"
    pkl_file = open(PROCESS_CACHE_FILE, 'rb')
    (allfonts, font_matrix) = pickle.load(pkl_file)
    pkl_file.close()
except:
    print "FAIL... build data and cache it"
    #make it from scratch

    print "removing null fonts"
    for f in allfonts:
        if isNullFont(f):
            allfonts.remove(f)

    print "done\n\n", len(allfonts), "fonts left\n"


    """
    #this code is an attempt to find out if distance == 0 is a good indicator of fonts
    # that will cause distance calculation segfaults if we use cvMatchContourTrees
    #
    # UPDATE: it only found 2 suspect fonts when there are at least 100 in there
    for i, font in enumerate(allfonts):
        if i == 0: continue
        if 0 == fontDistance(allfonts[i], allfonts[0]):
            print allfonts[i], "is suspect"
            break

            """


    font_matrix = makeFontMatrix(allfonts)

    output = open(PROCESS_CACHE_FILE, 'wb')
    pickle.dump((allfonts, font_matrix), output, -1)
    output.close()

#makeFontWebPages(allfonts, font_matrix)

somefonts = allfonts

#reduced set for test runs
"""
if False:
    reducto = 100
    somefonts = allfonts[:reducto]
    font_matrix = font_matrix[:reducto]
    for i, r in enumerate(font_matrix):
        font_matrix[i] = r[:reducto]

"""

(somefonts, font_matrix) = deZeroify(somefonts, font_matrix)
(somefonts, font_matrix) = deMissingfontify(somefonts, font_matrix)

try:
    print "Attempting to load tree from cache"
    pkl_file = open(TREE_CACHE_FILE, 'rb')
    tree = pickle.load(pkl_file)
    pkl_file.close()
except:
    print "Fail... Building huge tree and caching it"
    tree = makeFontTree(somefonts, font_matrix)
    
    output = open(TREE_CACHE_FILE, 'wb')
    pickle.dump(tree, output, -1)
    output.close()


tree.printout(lambda x: allfonts[x])


def makeExampleImages(x):
    letters = "AaBbCc"
    fontname = somefonts[x]
    fontlabel = realFontName(somefonts[x]).replace("&", "&amp;")
    ret = "<span class='font_entry'>"
    for c in letters:
        ret = ret + "<img src='" + FONT_CACHE_DIR + "/" + fontname + "/" + c + CHAR_IMG_EXT + "' />"
 
    try:
        ret = ret + fontlabel + "</span>"
    except:
        print "fontlabel has type", type(fontlabel)
        raise

    return ret


def makeExampleText(x):
    fontname = realFontName(somefonts[x]).replace("&", "&amp;")
    css_fontname = fontname.replace("'", "\\000027")

    ret = "<span class='font_entry'><span class='font_text' style='font-family:\"" 
    ret = ret + css_fontname + "\"'>"
    for c in "AaBbCcDdEe":
        ret = ret + c
    return ret + "</span> (" + fontname + ")</span>"


f = open('tree.html', 'w')
f.write(makeHtmlHeader("FontClustr - Master Tree", 0))
f.write(tree.to_html(lambda x : "<a href='" + FONT_CACHE_DIR + "/" + somefonts[x] + "/index.html'>" + somefonts[x] + "</a>"))
f.write("</body></html>")
f.close()

f = open('tree_images.html', 'w')
f.write(makeHtmlHeader("FontClustr - Master Tree with Letter Images", 0))
f.write(tree.to_html(makeExampleImages))
f.write("</body></html>")
f.close()
 
f = open('tree_text.html', 'w')
f.write(makeFontClustrHeader())
f.write(tree.to_html(makeExampleText))
f.write("</body></html>")
f.close()
