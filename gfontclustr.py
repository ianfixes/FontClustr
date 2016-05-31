#!/usr/bin/env python

licenseText = """
FontClustr: a program that clusters fonts based on their appearance

Copyright (C) 2010 Ian Katz

This software was written by Ian Katz
contact: ifreecarve@gmail.com

You should have received a copy of the Apache 2.0 license
along with FontClustr.  If not, see <http://www.apache.org/licenses/LICENSE-2.0>
"""

import errno
import math
import os
import pickle
import string
import sys
import time
import traceback
import types

import wxversion
wxversion.select("2.8")
import wx
import sqlite3
import pygame
from fontTools import ttLib
from wx.lib.wordwrap import wordwrap

import fontclustr


DB_FILENAME = "fontclustr.db"

CHAR_IMG_SIZE = 200

CACHE_CHAR_LIMIT = 2000000


#exception for aborting
class FontclustrAbort(Exception):
    pass

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
            #c.execute("select count(*) from distance_char")
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
    def CheckFonts(self, fontlist, progress_callback, msg_callback, dialog_obj):
        c = self.db.cursor()
        c.execute("update font set present = 0")
        i = 0

        self.mkdir(fontclustr.FONT_CACHE_DIR)

        for f in fontlist:
            #prep db record
            fontobject = fontclustr.cv_font(self.FullCharset(), f, CHAR_IMG_SIZE)
            rfn = fontobject.realName()
            font_id = 0

            #we can skip this
            (_, skip) = progress_callback(i, rfn)
            if skip: 
                dialog_obj.success = False
                return

            c.execute("select font_id from font where pygame_name = ?", (f,))
            row = c.fetchone()
            

            if None == row:
                c.execute("insert into font(name, pygame_name, present, ok) values(?,?,1,0)", (rfn, f))
                c.execute("select last_insert_rowid()")
                row = c.fetchone()
                #print "got", row
                font_id = row[0]
            else:
                font_id = row[0]
                c.execute("update font set name=?, present=1, ok=0 where font_id=?", (rfn, font_id))

            try:
                if fontobject.is_missing():
                    msg_callback("is-missing\t" + f)
                    continue

                both_names = f + " (" + fontobject.realName() + ")"

                fontobject.cache()

                if fontobject.is_null():
                    msg_callback("same-char\t" + both_names)
                    continue

                c.execute("update font set ok=1 where font_id=?", (font_id,))

            except OSError:
                raise
            except RuntimeError as inst:
                magickerr = "Magick: geometry does not contain image"
                ri = repr(inst)
                pos = ri.find(magickerr)
                if -1 != pos:
                    pth = ri[pos + len(magickerr):ri.find("@")]
                    msg_callback("blank-char\t" + both_names)
                elif -1 != ri.find("Text has zero width"):
                    msg_callback("zero-width\t" + both_names)
                else:
                    msg_callback(both_names + "\tRUNTIME ERROR: " + ri)
            except fontclustr.BlankChar:
                msg_callback("blank-char\t" + both_names)
            except Exception as inst:
                e_t = str(type(inst))
                e_r = repr(inst)

                helpful = e_t + "::" + e_r
                msg_callback(both_names + "\tERROR: " + helpful)

                #raise


            i = i + 1

        self.db.commit()





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

        return list("AaBbCcGgHhKkOoPpTtXx")
        #return list(fc + "1234567890")    


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


    def CreateMatrix(self, metric_id, charset_id, progress_callback, msg_callback, dialog_obj):
        print "in CreateMatrix"
        mycache = {} # speeds up font distance comparisons
        def getCachedFont(pygame_name):
            if pygame_name in mycache:
                pass 
                #print "hit!\t\t", pygame_name
            else:
                #print "\tmiss!\t" + pygame_name
                if CACHE_CHAR_LIMIT < len(self.FullCharset()) * len(mycache):
                    rmkey = mycache.keys()[0]
                    del mycache[rmkey]
                mycache[pygame_name] = fontclustr.cv_font(self.CharsetOf(charset_id), pygame_name, CHAR_IMG_SIZE)
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
                                and distance_font.charset_id = ?
                                and distance_font.imgsize_px = ?)
        """, (metric_id, charset_id, CHAR_IMG_SIZE))

        donework = 0
        for row in c:
            # if distance exists, use it... otherwise cache it
            afont_id = row[0]
            bfont_id = row[1]
            distance = row[2]
            i = id2idx[afont_id]
            j = id2idx[bfont_id]
            
            mylabel = font_list[i]["name"] + " vs " + font_list[j]["name"]
            #print mylabel
            (dialog_obj.fontclustr_continue, skipit) = progress_callback(donework, mylabel)

            if not dialog_obj.fontclustr_continue:
                return matrix, id2idx

            if not distance is None:
                pass 
                #print "DB!"
            else:
                f1 = getCachedFont(font_list[i]["pygame_name"])
                f2 = getCachedFont(font_list[j]["pygame_name"])

                distance = f1.distance_from(f2)

                c2.execute("""
                    insert into distance_font(a_font_id, 
                                              b_font_id, 
                                              metric_id, 
                                              charset_id, 
                                              imgsize_px, 
                                              distance)
                    values(?, ?, ?, ?, ?, ?)
                    """, (afont_id, bfont_id, metric_id, charset_id, CHAR_IMG_SIZE, distance))
                
            matrix[i][j] = distance
            matrix[j][i] = distance
            donework = donework + 1

            #commit every so often
            if 0 == donework % 100:
                #print "COMMIT"
                self.db.commit()

        c.close()
        c2.close()
        return matrix, id2idx




class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)

        self.fonts_loaded = False

        pygame.init ()

        self.setupMenu()
        self.setupScreen()
        self.Show(1)
        self.LogItem("Initialized")

        self.loadDatabase()


        #fixme: font metric / charset selections

        self.loadFonts()
        
        #self.loadMatrix()

    def loadDatabase(self):
        self.fontdb = FontDB()
        self.LogItem("Loading database")
        self.fontdb.LoadDB(DB_FILENAME)
        self.LogItem("Checking DB structure")
        self.fontdb.CheckDBStructure(self.LogItem)

        
    def loadFonts(self):
        if self.fonts_loaded: return

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
                                | wx.PD_CAN_SKIP
                                )
        dlg.SetSize((600,100))

        dlg.success = True

        self.fontdb.CheckFonts(allfonts, dlg.Update, self.LogItem, dlg)
        dlg.Destroy()
        if dlg.success:
            self.LogItem("Loading and caching complete")
        else:
            self.LogItem("Loading and caching aborted")
        wx._misc.Sleep(0.1)
        self.fonts_loaded = dlg.success


    def loadMatrix(self):
        self.loadFonts()
        if not self.fonts_loaded:
            self.LogItem("Can't proceed without loading fonts first")
            return
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
                                | wx.PD_CAN_ABORT
                                )
        dlg.fontclustr_continue = True
        dlg.SetSize((600,100))

        try:
            self.matrix, self.id2idx = self.fontdb.CreateMatrix(1, 1, dlg.Update, self.LogItem, dlg)

            if not dlg.fontclustr_continue:
                print "User aborted"
                dlg.Destroy()
                return False
            
            self.LogItem("Fonts loaded into matrix form")
            dlg.Destroy()
            return True
        
        except Exception as inst:
            self.LogItem(traceback.format_exc(inst))
            dlg.Destroy()
            return False

        
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
        menu1.Append(wx.ID_NEW, "New Choice", "Thing")
        menu1.AppendSeparator()
        menu1.Append(wx.ID_EXIT, "Exit", "Quit the program")
        menu2.Append(wx.ID_ABOUT, "About", "Find out who is responsible for this")
        menuBar = wx.MenuBar()
        menuBar.Append(menu1, "File")
        menuBar.Append(menu2, "Help")
        self.SetMenuBar(menuBar)
        self.Bind(wx.EVT_MENU, self.menuNewThing, id=wx.ID_NEW)
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
        

            
    def menuNewThing(self,e):
        self.loadMatrix()

        
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
