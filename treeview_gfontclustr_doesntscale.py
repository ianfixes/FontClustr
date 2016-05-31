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
import sqlite3
import string
import sys
import time

import numpy
import pygame
import PythonMagick
import wxversion
wxversion.select("2.8")
import wx
from wx.lib.wordwrap import wordwrap
from fontTools import ttLib


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

        c.close()

    #check that fonts in the db match the supplied list
    def LoadFonts(self, fontlist, progress_callback, msg_callback):
        c = self.db.cursor()
        c.execute("update font set present = 0")
        i = 0
        for f in fontlist:
            #prep db record
            n = self.realFontName(f)
            font_id = 0
            progress_callback(i, n)
            c.execute("select font_id from font where pygame_name = ?", [f])
            row = c.fetchone()

            if None == row:
                c.execute("insert into font(name, pygame_name, present, ok) values(?,?,1,0)", (n, f))
                c.execute("select last_insert_rowid()")
                row = c.fetchone()
                print "got", row
                font_id = row[0]
            else:
                font_id = row[0]
                c.execute("update font set name=?, present=1, ok=0 where font_id=?", (n, font_id))

            if self.CacheFont(f, msg_callback):
                c.execute("update font set ok=1 where font_id=?", [font_id])
            i = i + 1

        self.db.commit()


    def GetFontList(self):
        c = self.db.cursor()
        c.execute("select pygame_name, name from font where ok = 1 order by pygame_name asc")
        ret = []
        for row in c:
            ret.append(row)
        c.close()
        return ret

    @staticmethod
    def FullCharset():
        uc = string.uppercase
        lc = string.lowercase
        fc = ""
        for i, c in enumerate(uc):
            fc = fc + c + lc[i]

        return list(fc + "1234567890")


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
    def CacheFont(self, fontname, msg_callback):

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

            #FIXME: double this up to create a 1 px black border... should fix "elegante" problem
            img.crop(newbb)
            img.write(outname)


        fontdir = FONT_CACHE_DIR + os.path.sep + fontname
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
            for i, c in enumerate (FontDB.FullCharset()):
                outname = fontdir + os.path.sep + c + CHAR_IMG_EXT
                renderChar(font, c, outname)

            #trim the images
            for i, c in enumerate (FontDB.FullCharset()):
                outname = fontdir + os.path.sep + c + CHAR_IMG_EXT
                centerChar(outname)

            #mark as done
            self.mkdir(doneflag)

        except KeyboardInterrupt:
            raise
        except:
            msg_callback("Error " + str(sys.exc_info()[0]) + "caching " +  self.realFontName(fontname))
            #raise # if we want to find out what actually went wrong
            return False
        else:
            return True

    def mkdir(self, path):
        try:
            os.mkdir(path)
        except OSError, err:
            if err.errno != errno.EEXIST:
                raise

class TreePanel(wx.Panel):
    def __init__(self, parent):
        # Use the WANTS_CHARS style so the panel doesn't eat the Return key.
        wx.Panel.__init__(self, parent, -1, style=wx.WANTS_CHARS)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        tID = wx.NewId()

        self.tree = wx.TreeCtrl(self, tID, wx.DefaultPosition, wx.DefaultSize,
                                wx.TR_DEFAULT_STYLE
                                #wx.TR_HAS_BUTTONS
                                #| wx.TR_EDIT_LABELS
                                #| wx.TR_MULTIPLE
                                #| wx.TR_HIDE_ROOT
                                )

        isz = (32,32)
        isz = (12,12)
        il = wx.ImageList(isz[0], isz[1])
        self.il = il
        self.isz = isz
        self.tree.SetImageList(il)
        #self.Bind(wx.EVT_TREE_ITEM_EXPANDED, self.OnItemExpanded, self.tree)
        #self.Bind(wx.EVT_TREE_ITEM_COLLAPSED, self.OnItemCollapsed, self.tree)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnSelChanged, self.tree)
        #self.Bind(wx.EVT_TREE_BEGIN_LABEL_EDIT, self.OnBeginEdit, self.tree)
        #self.Bind(wx.EVT_TREE_END_LABEL_EDIT, self.OnEndEdit, self.tree)
        self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnActivate, self.tree)

        #self.tree.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        #self.tree.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        #self.tree.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)



    def LoadItems(self, fonttree, fontdb):
        # NOTE:  For some reason tree items have to have a data object in
        #        order to be sorted.  Since our compare just uses the labels
        #        we don't need any real data, so we'll just use None below for
        #        the item data.


        def LoadFontTree(atree, current_root):

            def AddFontInfo(wxitem, treenode):
                self.tree.SetItemText(wxitem, "AaBbCcDdEe")
                f = wx.Font(30, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False)
                (_, fontface) = flist[treenode.ptr]
                f.SetFaceName(fontface)
                self.tree.SetItemFont(wxitem, f)
                self.tree.SetPyData(wxitem, None)


            if TREE_LEAF == atree.type():
                item = self.tree.AppendItem(current_root, "rhubarb")
                AddFontInfo(item, atree)
            else:
                child = self.tree.AppendItem(current_root, "")
                self.tree.SetPyData(child, None)
                self.tree.SetItemImage(child, fldridx, wx.TreeItemIcon_Normal)
                self.tree.SetItemImage(child, fldropenidx, wx.TreeItemIcon_Expanded)
                if TREE_LEAF == atree.lt.type():
                    AddFontInfo(child, atree.lt)
                    LoadFontTree(atree.rt, child)
                elif TREE_LEAF == atree.rt.type():
                    AddFontInfo(child, atree.rt)
                    LoadFontTree(atree.lt, child)
                else:
                    LoadFontTree(atree.lt, child)
                    LoadFontTree(atree.rt, child)
                self.tree.Expand(child)

        il = self.il
        isz = self.isz
        fldridx     = il.Add(wx.ArtProvider_GetBitmap(wx.ART_FOLDER,      wx.ART_OTHER, isz))
        fldropenidx = il.Add(wx.ArtProvider_GetBitmap(wx.ART_FILE_OPEN,   wx.ART_OTHER, isz))
        fileidx     = il.Add(wx.ArtProvider_GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, isz))

        self.root = self.tree.AddRoot("The Root Item")
        self.tree.SetPyData(self.root, None)
        self.tree.SetItemImage(self.root, fldridx, wx.TreeItemIcon_Normal)
        self.tree.SetItemImage(self.root, fldropenidx, wx.TreeItemIcon_Expanded)

        flist = fontdb.GetFontList()

        LoadFontTree(fonttree, self.root)

        self.tree.Expand(self.root)



    def OnRightDown(self, event):
        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        if item:
            print("OnRightClick: %s, %s, %s\n" %
                               (self.tree.GetItemText(item), type(item), item.__class__))
            self.tree.SelectItem(item)


    def OnRightUp(self, event):
        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        if item:
            print("OnRightUp: %s (manually starting label edit)\n"
                               % self.tree.GetItemText(item))
            self.tree.EditLabel(item)



    def OnBeginEdit(self, event):
        print("OnBeginEdit\n")
        # show how to prevent edit...
        item = event.GetItem()
        if item and self.tree.GetItemText(item) == "The Root Item":
            wx.Bell()
            print("You can't edit this one...\n")

            # Lets just see what's visible of its children
            cookie = 0
            root = event.GetItem()
            (child, cookie) = self.tree.GetFirstChild(root)

            while child.IsOk():
                print("Child [%s] visible = %d" %
                                   (self.tree.GetItemText(child),
                                    self.tree.IsVisible(child)))
                (child, cookie) = self.tree.GetNextChild(root, cookie)

            event.Veto()


    def OnEndEdit(self, event):
        print("OnEndEdit: %s %s\n" %
                           (event.IsEditCancelled(), event.GetLabel()) )
        # show how to reject edit, we'll not allow any digits
        for x in event.GetLabel():
            if x in string.digits:
                print("You can't enter digits...\n")
                event.Veto()
                return


    def OnLeftDClick(self, event):
        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        if item:
            print("OnLeftDClick: %s\n" % self.tree.GetItemText(item))
            parent = self.tree.GetItemParent(item)
            if parent.IsOk():
                self.tree.SortChildren(parent)
        event.Skip()


    def OnSize(self, event):
        w,h = self.GetClientSizeTuple()
        self.tree.SetDimensions(0, 0, w, h)


    def OnItemExpanded(self, event):
        item = event.GetItem()
        if item:
            print("OnItemExpanded: %s\n" % self.tree.GetItemText(item))

    def OnItemCollapsed(self, event):
        item = event.GetItem()
        if item:
            print("OnItemCollapsed: %s\n" % self.tree.GetItemText(item))

    def OnSelChanged(self, event):
        self.item = event.GetItem()
        if self.item:
            print("OnSelChanged: %s\n" % self.tree.GetItemText(self.item))
            if wx.Platform == '__WXMSW__':
                print("BoundingRect: %s\n" %
                                   self.tree.GetBoundingRect(self.item, True))
            #items = self.tree.GetSelections()
            #print map(self.tree.GetItemText, items)
        event.Skip()


    def OnActivate(self, event):
        if self.item:
            print("OnActivate: %s\n" % self.tree.GetItemText(self.item))




class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)

        pygame.init ()

        self.setupMenu()
        self.setupScreen()
        self.Show(1)
        self.LogItem("Initialized")

        self.loadDatabase()
        self.loadFonts()

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

        self.fontdb.LoadFonts(allfonts, dlg.Update, self.LogItem)
        dlg.Destroy()
        self.LogItem("Loading and caching complete")
        wx._misc.Sleep(0.1)


        TREE_CACHE_FILE = FONT_CACHE_DIR + os.path.sep + "master_tree.pkl"

        fonttree = None
        #try:
        self.LogItem("Attempting to load tree from cache")
        pkl_file = open(TREE_CACHE_FILE, 'rb')
        fonttree = pickle.load(pkl_file)
        pkl_file.close()
        #except:
        #    print "ERROR'D"

        self.tree.LoadItems(fonttree, self.fontdb)




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

        #row1 = wx.StaticBoxSizer(wx.StaticBox(self, -1, label = "Log"), wx.VERTICAL)
        row1 = wx.BoxSizer(wx.HORIZONTAL)

        self.log = wx.TextCtrl(self, -1, style = wx.TE_MULTILINE | wx.TE_READONLY)
        row1.Add(self.log, 1, wx.EXPAND)


        self.tree = TreePanel(self)

        main_sizer.Add(row1, 0, wx.EXPAND)
        main_sizer.Add(self.tree, 1, wx.EXPAND)

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
