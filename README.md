FontClustr
==========

FontClustr was conceived in January 2010 by Ian Katz.
 ifreecarve@gmail.com / http://tinylittlelife.org

It uses computer vision algorithms to sort fonts by appearance.

FontClustr is free software licensed under the terms of the GPLv3.


Installation
============

FontClustr is written in Python 2 and requires the following libraries:

- fonttools
- numpy
- opencv
- Python Imaging Library (or Pillow)
- pygame



Linux Support
-------------

Tested in Ubuntu 10.10, requiring the following packages:
 python-pygame
 python-opencv
 python-numpy
 python-imaging
 fonttools

Probably other packages, your feedback is appreciated.


OSX Support
-----------

You need to install opencv, and this is currently BROKEN.

You need a python2.6 virtualenv.  

You need to edit the bin/activate script of that virtualenv to add:
 alias python='arch -i386 python'

You need to pip install:
 PIL
 pygame
 numpy



Usage
=====

Run FontClustr as "python fontclustr.py" or make `fontclustr.py` executable and run it directly.

There is experimental support for a GUI version of FontClustr called `gfontclustr.py` that caches results. 

Right now, it sucks.  Eventually it will be interactive.  "python gfontclustr.py"

