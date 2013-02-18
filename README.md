FontClustr
==========

FontClustr was conceived in January 2010 by Ian Katz.
 ifreecarve@gmail.com / http://tinylittlelife.org

It uses computer vision algorithms to sort fonts by appearance.

Running it
==========

Run FontClustr as "python fontclustr.py" or make fontclustr.py executable and run it directly.

There is experimental support for a GUI version of FontClustr that caches results. 
Right now, it sucks.  Eventually it will be interactive.  "python gfontclustr.py"


Linux Support
=============

Tested in Ubuntu 10.10, requiring the following packages:
 python-pygame
 python-opencv
 python-numpy
 python-imaging
 fonttools

Probably other stuff that I can't think of right now.

OSX Support
===========

You need a python2.6 virtualenv.  

You need to edit the bin/activate script of that virtualenv to add:
 alias python='arch -i386 python'

You need to pip install:
 PIL
 pygame
 numpy

You need to install opencv, and this is currently BROKEN.
