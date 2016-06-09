FontClustr
==========

FontClustr was conceived in January 2010 by Ian Katz.
 ifreecarve@gmail.com / http://tinylittlelife.org

It uses computer vision algorithms to sort fonts by appearance.

FontClustr is free software licensed under the terms of the Apache 2.0 license.


Installation
============

FontClustr is written in Python 2 and JavaScript.  It requires the following libraries:


### Python

- fonttools
- opencv
- Python Imaging Library (or Pillow)
- numpy


### JavaScript

Running `npm install` will fetch the following dependencies:

- d3
- markov-cluster
- minimist



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

You need to install opencv; I used the instructions here:
https://jjyap.wordpress.com/2014/05/24/installing-opencv-2-4-9-on-mac-osx-with-python-support/

You need to pip install:
 PIL
 numpy
 fonttools

Usage
=====

### New Way

* Run `python fontclustr_json.py`.  This will generate a cache and a distance matrix, and save them for future use.
* Run `node index.js report/distance_information_AaBbCcGgHhKkOoPpTtXx.json report/allClusters.json`.  This will calculate the clusters using a hacked approach to the Markov Clustering algorithm
* Run `python -m SimpleHTTPServer 9999`
* Open http://localhost:9999/report/ in a web browser



### Old Way

Run FontClustr as "python fontclustr.py" or make `fontclustr.py` executable and run it directly.

There is experimental support for a GUI version of FontClustr called `gfontclustr.py` that caches results.

Right now, it sucks.  Eventually it will be interactive.  "python gfontclustr.py"
