#!/usr/bin/env python

licenseText = """
FontClustr: a program that clusters fonts based on their appearance

Copyright (C) 2010 Ian Katz

This software was written by Ian Katz
contact: ifreecarve@gmail.com

FontClustr is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

FontClustr is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with FontClustr.  If not, see <http://www.gnu.org/licenses/>.
"""

import wxversion
wxversion.select("2.8")

import wx
import sqlite3
import sys 
import os
import errno
import math
import PythonMagick
import pygame
import string
import numpy
import time 
import pygame
import pickle

from wx.lib.wordwrap import wordwrap
from fontTools import ttLib
from opencv import cv
from opencv import highgui


DB_FILENAME = "fontclustr.db"



class CharsetChooser(wx.MultiChoiceDialog):
    def __init__(self, parent, charset_name):
        wx.MultiChoiceDialog.__init__(self, parent, "Select characters for %s" % charset_name, FontDB.FullCharset())

    def SetSelectedCharset(self, charset_contents):
        selected = []
        for i, c in enumerate(FontDB.FullCharset()):
            if c in charset_contents:
                selected.append(i)  
 
        self.SetSelections(selected)

    def GetSelectedCharset(self):
        fc = FontDB.FullCharset()
        chars = [fc[x] for x in self.GetSelections()]
        return "".join(chars)

    """
        dlg = CharsetChooser(wx.MultiChoiceDialog(self, charset_name)
        dlg.SetSelectedCharset("ABCwhatever" or charset_contents)

        if (dlg.ShowModal() == wx.ID_OK):
            new_charset = dlg.GetSelectedCharset()
            if 0 == len(new_charset):
                # error message
            else:
                # write new_charset to db

        dlg.Destroy()
     """


FONT_CACHE_DIR = "cache"
CHAR_IMG_EXT = ".bmp"
CHAR_IMG_SIZE = 100
SAFETY_MARGIN = 0.85
CACHE_LIMIT = 1200000

class FontDB(object):
    def __init__(self):
        self.db = None

    def LoadDB(self, sqlite3_file):
        self.db = sqlite3.connect(sqlite3_file)
        #self.db.isolation_level = None

    #basic check that the schema has been set up properly, and reload if necessary
    def CheckDBStructure(self, msg_callback):
        c = self.db.cursor()
        try:
            c.execute("select count(*) from font")
            c.execute("select count(*) from metric")
            c.execute("select count(*) from charset")
            c.execute("select count(*) from distance_font")
            c.execute("select count(*) from distance_char")
            msg_callback("DB Structure OK")
        except:
            msg_callback("Error with structure, trashing DB and rebuilding")
            c.executescript(open("schema_fontclustr.sql").read())

            #initial values for the sole comparison method i'm using
            charset = "".join(self.FullCharset())
            c.execute("insert into charset(charset_id, name, contents) values(1, 'Full Set', ?)", (charset,))
            c.execute("insert into metric(metric_id, name) values(1, 'ContourMatchI2')")
            self.db.commit()

        c.close()

    #check that fonts in the db match the supplied list
    def CheckFonts(self, fontlist, progress_callback, msg_callback):
        c = self.db.cursor()
        c.execute("update font set present = 0")
        i = 0
        for f in fontlist:
            #prep db record
            n = self.realFontName(f)
            font_id = 0
            progress_callback(i, n)
            c.execute("select font_id from font where pygame_name = ?", (f,))
            row = c.fetchone()

            if None == row:
                c.execute("insert into font(name, pygame_name, present, ok) values(?,?,1,0)", (n, f))
                c.execute("select last_insert_rowid()")
                row = c.fetchone()
                #print "got", row
                font_id = row[0]
            else:
                font_id = row[0]
                c.execute("update font set name=?, present=1, ok=0 where font_id=?", (n, font_id))

            try:
                if self.CacheFontImages(f, msg_callback):
                    if not self.isNullFont(f, msg_callback):
                        if not self.isMissingFont(f, msg_callback):
                            c.execute("update font set ok=1 where font_id=?", (font_id,))
            except OSError:
                raise
            except Exception as inst:
                msg_callback(f + " errored with " + str(type(inst)))
                raise

            i = i + 1

        self.db.commit()


    #if all the font characters are the same (probably boxes) the font is useless
    def isNullFont(self, fontname, msg_callback):
        c0 = cv_char(fontname, self.FullCharset()[0])
        for c in self.FullCharset()[1:]:
            if 0 < c0.contour_distance_from(cv_char(fontname, c)):
                return False
        msg_callback(fontname + " seems null")
        return True

    #if the font file can't be found, it's probably useless
    def isMissingFont(self, fontname, msg_callback):
        if None is pygame.font.match_font(fontname):
            msg_callback(fontname + " seems to be missing its font file")
            return True
        return False

    #get a list of records {font_id, pygame_name, name} of REASONABLE fonts
    def GetFontList(self):
        c = self.db.cursor()
        c.execute("select font_id, pygame_name, name from font where ok = 1")
        ret = []
        for row in c:
            ret.append({"font_id": row[0], "pygame_name": row[1], "name": row[2]})
        c.close()
        return ret

    #our character set in list form
    @staticmethod
    def FullCharset():
        uc = string.uppercase
        lc = string.lowercase
        fc = ""
        for i, c in enumerate(uc):
            fc = fc + c + lc[i]

        return list(fc + "1234567890")    

    @staticmethod
    def fontDir(fontname):
        return FONT_CACHE_DIR + os.path.sep + fontname

    @staticmethod
    def charFile(fontname, charname):
        return str(FontDB.fontDir(fontname) + os.path.sep + charname + CHAR_IMG_EXT)

    # turn pygame's "arialblack" into "Arial Black" so browsers can use it
    def realFontName(self, afont):
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

        fontfile = pygame.font.match_font(afont)
        try:
            return unicode(shortName(ttLib.TTFont(fontfile))[1]) #seems to work better
            #return shortName(ttLib.TTFont(fontfile))[0]
        except:
            return unicode(afont)


    #make images from each character of a font
    #pygame fontname!
    def CacheFontImages(self, fontname, msg_callback):

        self.mkdir(FONT_CACHE_DIR)

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

            if CHAR_IMG_SIZE < bb.width and CHAR_IMG_SIZE < bb.height():
                #simple case, just crop
                newbb = PythonMagick._PythonMagick.Geometry(
                    CHAR_IMG_SIZE, 
                    CHAR_IMG_SIZE, 
                    bb.xOff() - ((CHAR_IMG_SIZE - bb.width()) / 2),
                    bb.yOff() - ((CHAR_IMG_SIZE - bb.height()) / 2),
                    )
                img.crop(newbb)
            else:
                #difficult case, crop aggressively then back off
                newbb = PythonMagick._PythonMagick.Geometry(
                    CHAR_IMG_SIZE - 2, 
                    CHAR_IMG_SIZE - 2, 
                    bb.xOff() - (((CHAR_IMG_SIZE - 2) - bb.width()) / 2),
                    bb.yOff() - (((CHAR_IMG_SIZE - 2) - bb.height()) / 2),
                    )
                img.crop(newbb)

                #newbb2 = PythonMagick._PythonMagick.Geometry(CHAR_IMG_SIZE, CHAR_IMG_SIZE, 1, 1)
                #img.crop(newbb2)

            img.write(outname)


        fontdir = self.fontDir(fontname)
        doneflag = fontdir + os.path.sep + "done"

        if os.path.exists(doneflag):
            #print "skipping", percentdone, fontname
            return True

        try:
            self.mkdir(fontdir)

            font = pygame.font.Font(pygame.font.match_font(fontname), 
                                    int(math.floor(CHAR_IMG_SIZE * SAFETY_MARGIN))
                                    )

            #make the images
            for i, c in enumerate (self.FullCharset()):
                renderChar(font, c, self.charFile(fontname, c))

            #trim the images ... do this separately just in case of errors in the first part
            for i, c in enumerate (self.FullCharset()):
                centerChar(self.charFile(fontname, c))

            #mark as done... works unless user decides to delete some but not all dir contents
            self.mkdir(doneflag)

        except KeyboardInterrupt:
            raise
        except:
            msg_callback("Error " + str(sys.exc_info()[0]) + " caching " +  self.realFontName(fontname))
            raise # uncomment here if we want to find out what actually went wrong
            return False
        else:
            return True


    def mkdir(self, path):
        try:
            os.mkdir(path)
        except OSError, err:
            if err.errno != errno.EEXIST:
                raise


    def FontInfoOf(self, font_id):
        c = self.db.cursor()
        c.execute("select name, pygame_name from font where font_id = ?", (font_id,))
        row = c.fetchone()
        c.close()
        return row


    def CharsetOf(self, charset_id):
        c = self.db.cursor()
        c.execute("select contents from charset where charset_id = ?", (charset_id,))
        row = c.fetchone()
        c.close()
        return row[0]


    def CreateMatrix(self, metric_id, charset_id, progress_callback, msg_callback):
        mycache = {} # speeds up font distance comparisons
        def getCachedFont(pygame_name):
            if not pygame_name in mycache:
                if CACHE_LIMIT < len(self.FullCharset()) * len(mycache) * CHAR_IMG_SIZE:
                    rmkey = mycache.keys()[0]
                    del mycache[rmkey]
                mycache[pygame_name] = cv_font(self.CharsetOf(charset_id), pygame_name)
            return mycache[pygame_name]

        #get font list and make a lookup table
        font_list = self.GetFontList()
        numfonts = len(font_list)
        id2idx = {}
        for i, font in enumerate(font_list):
            id2idx[font["font_id"]] = i
            
        #initialize matrix to all 0's, get the cached distances from DB (plus holes)
        matrix = [[0 for col in range(numfonts)] for row in range(numfonts)]

        c = self.db.cursor()
        c2 = self.db.cursor()
        progress_callback(0, "Caching distances")
        c.execute(
        """
        select fontpairs.afont_id, 
               fontpairs.bfont_id, 
               distance_font.distance 
        from (
            select afont.font_id afont_id, 
                   bfont.font_id bfont_id 
            from font as afont, 
                 font as bfont 
            where afont.ok <> 0 
              and bfont.ok <> 0
              and afont.font_id < bfont.font_id
            ) fontpairs 
        left join distance_font on (distance_font.a_font_id = fontpairs.afont_id 
                                and distance_font.b_font_id = fontpairs.bfont_id 
                                and distance_font.metric_id = ? 
                                and distance_font.charset_id = ?)
        """, (metric_id, charset_id))

        donework = 0
        for row in c:
            # if distance exists, use it... otherwise cache it
            afont_id = row[0]
            bfont_id = row[1]
            distance = row[2]
            i = id2idx[afont_id]
            j = id2idx[bfont_id]
            
            print font_list[i]["name"] + " vs " + font_list[j]["name"]
            progress_callback(donework, font_list[i]["name"] + " vs " + font_list[j]["name"])

            if None == distance:
                f1 = getCachedFont(font_list[i]["pygame_name"])
                f2 = getCachedFont(font_list[j]["pygame_name"])

                distance = f1.distance_from(f2)

                c2.execute("""
                    insert into distance_font(a_font_id, b_font_id, metric_id, charset_id, distance)
                    values(?,?,?,?,?)
                    """, (afont_id, bfont_id, metric_id, charset_id, distance))
                
            matrix[i][j] = distance
            matrix[j][i] = distance
            donework = donework + 1

            #commit every so often
            if 0 == donework % 100:
                self.db.commit()

        c.close()
        c2.close()
        return matrix, idx2id



        
class cv_char(object):
    def __init__(self, fontname, charname):
        self.c = charname
        self.fontname = fontname
        self.filename = FontDB.charFile(fontname, charname)

        self.img = None
        self.edg = None
        self.sto = None
        self.cnt = None
        self.tre = None


    #poor result
    def shape_distance_from(self, another_cv_char, match_method = cv.CV_CONTOURS_MATCH_I3):
        #match_method can also be cv.CV_CONTOURS_MATCH_I1 or I2
        return cv.cvMatchShapes(
            highgui.cvLoadImage(self.filename,            highgui.CV_LOAD_IMAGE_GRAYSCALE),
            highgui.cvLoadImage(another_cv_char.filename, highgui.CV_LOAD_IMAGE_GRAYSCALE),
            match_method,
            0,
            )

    def contour_distance_from(self, another_cv_char, 
                              method = cv.CV_CONTOURS_MATCH_I2, 
                              doLogPolar = False):
        #method can also be cv.CV_CONTOURS_MATCH_I1 or I3
        print "contour_distance_from", self.c, self.fontname, another_cv_char.c, another_cv_char.fontname
        self.make_contour(doLogPolar)
        another_cv_char.make_contour(doLogPolar)
        return cv.cvMatchShapes(self.cnt, another_cv_char.cnt, method, 0)


    # this method may be better, but causes a lot of crashes in the openCV library...
    def tree_distance_from(self, another_cv_char):
        self.make_tree()
        another_cv_char.make_tree()
        return cv.cvMatchContourTrees(self.tre, another_cv_char.tre, 1, 0)
        

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


    def make_contour(self, doLogPolar):
        if None != self.cnt:
            return

        self.img = highgui.cvLoadImage(self.filename, highgui.CV_LOAD_IMAGE_GRAYSCALE)
        if doLogPolar:
            self.img = toLogPolar(self.img)

        #image is already white on black, so i guess we dont need this
        #self.edg = cv.cvCreateImage(cv.cvGetSize(self.img), 8, 1)
        #cv.cvThreshold(self.img, self.edg, 1, 255, cv.CV_THRESH_BINARY)

        self.sto = cv.cvCreateMemStorage (0)
        nb_contours, self.cnt = cv.cvFindContours (self.img, #self.edg,
                                                        self.sto,
                                                        cv.sizeof_CvContour,
                                                        cv.CV_RETR_TREE,
                                                        cv.CV_CHAIN_APPROX_NONE,
                                                        cv.cvPoint (0,0))
        
        del self.img
        self.img = None
        return


    def make_tree(self):
        if None == self.img:
            self.make_contour()
        if None == self.tre:
            self.tre = cv.cvCreateContourTree(self.cnt, self.sto, 0)


class cv_font(object):
    def __init__(self, charset, fontname):
        self.charset = charset
        self.fontname = fontname
        self.chars = {}
        for c in self.charset:
            self.chars[c] = cv_char(self.fontname, c)
            
    def distance_from(self, another_cv_font):
        dist = 0
        for c in self.charset:
            dist = dist + self.chars[c].contour_distance_from(another_cv_font.chars[c])

        return dist





class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)

        pygame.init ()

        self.setupMenu()
        self.setupScreen()
        self.Show(1)
        self.LogItem("Initialized")

        self.loadDatabase()
        #fixme: dialog with disk space, continue / exit
        self.loadFonts()
        #fixme: font metric / charset selections
        #fixme: will now generate font tree + matrix, continue / exit
        
        self.loadMatrix()

    def loadDatabase(self):
        self.fontdb = FontDB()
        self.LogItem("Loading database")
        self.fontdb.LoadDB(DB_FILENAME)
        self.LogItem("Checking DB structure")
        self.fontdb.CheckDBStructure(self.LogItem)

        
    def loadFonts(self):
        allfonts = pygame.font.get_fonts()
        allfonts.sort()

        self.LogItem("Loading font list and caching images - a few errors here is normal")

        dlg = wx.ProgressDialog("Loading Fonts",
                               "An informative message",
                               maximum = len(allfonts),
                               parent = self,
                               style = wx.PD_APP_MODAL
                                | wx.PD_ELAPSED_TIME
                                #| wx.PD_ESTIMATED_TIME
                                | wx.PD_REMAINING_TIME
                                )
            
        self.fontdb.CheckFonts(allfonts, dlg.Update, self.LogItem)
        dlg.Destroy()
        self.LogItem("Loading and caching complete")
        wx._misc.Sleep(0.1)


    def loadMatrix(self):
        self.LogItem("Calculating font distances - this may take a while")

        numfonts = len(self.fontdb.GetFontList())
        totalwork = (numfonts ** 2. - numfonts) / 2

        dlg = wx.ProgressDialog("Calculating Distances",
                               "An informative message",
                               maximum = totalwork,
                               parent = self,
                               style = wx.PD_APP_MODAL
                                | wx.PD_ELAPSED_TIME
                                #| wx.PD_ESTIMATED_TIME
                                | wx.PD_REMAINING_TIME
                                )
            
        self.matrix, self.id2idx = self.fontdb.CreateMatrix(1, 1, dlg.Update, self.LogItem)
        dlg.Destroy()
        self.LogItem("Fonts loaded into matrix form")


        
    def setupScreen(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)        

        """
        column1 = wx.BoxSizer(wx.VERTICAL)
        column2 = wx.BoxSizer(wx.VERTICAL)
        column3 = wx.BoxSizer(wx.VERTICAL)


        column3.Add( SOME_CLASS(self, ...), 1, wx.EXPAND | wx.BORDER)

        main_sizer.Add(column1, 1, wx.EXPAND | wx.BORDER)        
        main_sizer.Add(column2, 1, wx.EXPAND | wx.BORDER)
        main_sizer.Add(column3, 1, wx.EXPAND | wx.BORDER)

    def makeSimpleBox3(win):
    box = wx.BoxSizer(wx.HORIZONTAL)
    box.Add(SampleWindow(win, "one"), 0, wx.EXPAND)
    box.Add(SampleWindow(win, "two"), 0, wx.EXPAND)
    box.Add(SampleWindow(win, "three"), 0, wx.EXPAND)
    box.Add(SampleWindow(win, "four"), 0, wx.EXPAND)
    box.Add(SampleWindow(win, "five"), 1, wx.EXPAND)


        self.SetSizerAndFit(main_sizer)
        self.SetSize((600,450))
        """

        row1 = wx.StaticBoxSizer(wx.StaticBox(self, -1, label = "Log"), wx.VERTICAL)
        #row1 = wx.BoxSizer(wx.HORIZONTAL)

        self.log = wx.TextCtrl(self, -1, style = wx.TE_MULTILINE | wx.TE_READONLY)
        row1.Add(self.log, 1, wx.EXPAND)
        
        main_sizer.Add(row1, 1, wx.EXPAND)

        self.SetSizerAndFit(main_sizer)


    def LogItem(self, item):
        self.log.AppendText(time.strftime("(%H:%M:%S) " + item + os.linesep))
        
        
    def setupMenu(self):
        ## Set Up The Menu
        menu1 = wx.Menu()
        menu2 = wx.Menu()
        # information string shows up in statusbar
        menu1.Append(wx.ID_NEW, "New Connection", "Connect to a MOOS Community")
        menu1.AppendSeparator()
        menu1.Append(wx.ID_EXIT, "Exit", "Quit the program")
        menu2.Append(wx.ID_ABOUT, "About", "Find out who is responsible for this")
        menuBar = wx.MenuBar()
        menuBar.Append(menu1, "File")
        menuBar.Append(menu2, "Help")
        self.SetMenuBar(menuBar)
        self.Bind(wx.EVT_MENU, self.menuNewConnection, id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self.menuExit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.menuAbout, id=wx.ID_ABOUT)
        ## End Menu

    def menuAbout(self, e):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = "FontClustr"
        info.Version = "1.2"
        info.Copyright = "(C) 2010 Ian Katz"
        info.Description = wordwrap("FontClustr uses computer vision to create "
            "clusters of fonts with similar appearance.  It was written in the "
            "hope that this approach will become the standard for font organization.",
            350, wx.ClientDC(self))
        info.WebSite = ("http://tinylittlelife.org/?page_id=255", "FontClustr home page")
        info.Developers = [ "Ian Katz" ]

        info.License = wordwrap(licenseText, 500, wx.ClientDC(self))

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)
        

            
    def menuNewConnection(self,e):
        pass
        
    def menuExit(self,e):
        print "Exit"
        self.Close()
        



TREE_BRANCH = 0
TREE_LEAF   = 1

class tree(object):
    def type(self):
        #the type of object
        pass

    def printout(self, leaf_func):
        def printout_h(atree, acc):
            if TREE_LEAF == atree.type():
                print acc, leaf_func(atree.ptr)
            else:
                printout_h(atree.lt, "-" + acc)
                printout_h(atree.rt, "=" + acc)

        printout_h(self, "")


    def num_leaves(self):
        #helper
        def num_leaves_h(atree, acc):
            if TREE_LEAF == atree.type():
                return acc + 1
            return num_leaves_h(atree.rt, num_leaves_h(atree.lt, acc))
        return num_leaves_h(self, 0)

    def leaves(self):
        #helper
        def leaves_h(atree, acc):
            if TREE_LEAF == atree.type():
                return acc.append(atree.value)
            return leaves_h(atree.rt, leaves_h(atree.lt, acc))
        return leaves_h(self, [])

    def has_loop(self):
        def has_loop_h(atree, acc, armed):
            if acc == atree and armed: return True
            if TREE_LEAF == atree.type(): return False
            return has_loop_h(atree.lt, acc, True) or has_loop_h(atree.rt, acc, True)

        return has_loop_h(self, self, False)


    def contains(self, ptr):
        if ptr == self: return true
        if TREE_LEAF == self.type(): return False
        return self.lt.contains(ptr) or self.rt.contains(ptr)
    

    def to_html(self, leaf_func):
        def to_html_h(atree, leaf_func, s):
            sp = s * " "
            if TREE_LEAF == atree.type():
                return sp + "<li>" + leaf_func(atree.ptr) + "</li>\n"
            else:
                ltside = sp + "<li><ul>\n" + to_html_h(atree.lt, leaf_func, s + 1) + sp + "</ul></li>\n"
                rtside = sp + "<li><ul>\n" + to_html_h(atree.rt, leaf_func, s + 1) + sp + "</ul></li>\n"
                return ltside + rtside
            
        return "<ul>\n" + to_html_h(self, leaf_func, 1) + "</ul>\n"
        

    # 
    # links to "far" fonts: how?
    # maybe mirror on the tree?
    # 
    # as we descend the tree, keep a pointer to the "other branch" when we call one side?
    # 
    """
    def namedSubtrees(self):
        def nst_h(atree, other_side, next_hop, acc):
            if TREE_LEAF == atree.type():
                #next_hop = the number of nodes that will be added if we jump to the parent
                return acc + [(atree.ptr, (other_side, next_hop))]
            else:
                new_next_hop = next_hop - atree.num_leaves()
                leftside = nst_h(atree.lt, atree.rt, new_next_hop, acc)
                rightside = nst_h(atree.rt, atree.lt, new_next_hop, leftside)
                return rightside

        nst_h(
       """         



class branch(tree):

    def __init__(self):
        pass

    def set_branches(self, lt, rt):
        self.lt = lt
        self.rt = rt
    
    def type(self):
        return TREE_BRANCH

    
class leaf(tree):
    
    def __init__(self):
        self.ptr = None

    def type(self):
        return TREE_LEAF




            
def GFontClustrMain():
    app = wx.App()
    frame = MainWindow(None, -1, "FontClustr: Better Font Organization")
    app.MainLoop()

if __name__ == "__main__":
    GFontClustrMain()
