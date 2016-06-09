var fs = require('fs');
var MCL = require('markov-cluster').MCL;
var stats  = require('./lib/stats.js');
var minimist = require('minimist');

var argv = minimist(process.argv.slice(1));

// Usage for the hapless user
if (argv._.length < 3) {
  console.dir(argv);
  throw new Error("Usage: <this script.js> <distanceInformation JSON file> <font tree JSON file>");
}

var distanceInformation = require('./' + argv._[1]);
var outputFilename = argv._[2];
console.dir(Object.keys(distanceInformation));

// make a huge hash of distance info, keyed on font name (what we give to MCL)
var data = {};
var fontNames = [];
for (var i = 0; i < distanceInformation.fonts.length; ++i) {
  var font = distanceInformation.fonts[i];
  fontNames.push(font.name);
  data[font.name] = {
    font: font,
    distanceTo: {}
  };

  // load up distances to other fonts from this font
  for (var j = 0; j < distanceInformation.fonts.length; ++j) {
    var otherFont = distanceInformation.fonts[j];
    data[font.name].distanceTo[otherFont.name] = distanceInformation.distances[i][j];
  }
}

// when clusters have overlap, remove the duplicate from whichver sets have more members
function deDuplicate(clusters) {
  var clusterLengths = [];
  var membership = {};
  var ret = [];

  // determine membership in clusters
  for (var i = 0; i < clusters.length; ++i) {
    var cluster = clusters[i];
    ret.push([]);
    clusterLengths[i] = cluster.length;
    for (var member of cluster) {
      if (member in membership) {
        membership[member].push(i);
      } else {
        membership[member] = [i];
      }
    }
  }

  // apply members back to clusters
  for (var member in membership) {
    var homes = membership[member];

    if (homes.length > 1) {
      console.log(member + " is in " + homes.length + " clusters");
    }

    // find out which cluster has the smallest size
    var newCluster = homes[0];
    var minSize = clusterLengths[newCluster];
    for (var i = 0; i < homes.length; ++i) {
      var nextClusterSize = clusterLengths[homes[i]];
      if (nextClusterSize < minSize) {
        newCluster = i;
        minSize = nextClusterSize;
      }
    }

    // now that we have the id of the smallest cluster, push the member
    ret[newCluster].push(member);
  }

  return ret;
}

function multiCluster(inputFontArray) {

  // get all distances for the fonts involved in this clustering operation
  var getDistances = function (inputArray) {
    var n = inputArray.length;
    var distances = [];
    for (var i = 0; i < n; ++i) {
      for (var j = i + 1; j < n; ++j) {
        distances.push(data[inputArray[i]].distanceTo[inputArray[j]]);
      }
    }
    return distances;
  }

  // build and solve an MCL using a threshold for the edge distance
  var getClusters = function (inputArray, threshold) {
    var n = inputArray.length;
    var mcl = new MCL({loopLimit: 100});
    for (var i = 0; i < n; ++i) {
      var oneFont = inputArray[i];
      for (var j = i + 1; j < n; ++j) {
        var otherFont = inputArray[j];
        var dist = data[oneFont].distanceTo[otherFont];
        if (dist < threshold) {
          mcl.setEdge(oneFont, otherFont, dist);
        }

      }
    }
    return mcl.clustering();
  }

  var multiClusterHelper = function (inputArray, initialQuantile) {
    var n = inputArray.length;

    // MCL wants to see some disconnected nodes, so pick an arbitrary threshold of 0.4 (quantile)
    // and if we can't split into more than one cluster with that, divide in half until we do
    var threshold = 0.8;
    var quantile = null;
    var distances = getDistances(inputArray);

    // further, we know that if a previous iteration needed to constrain to a certain distance
    // then we will have to be tighter than that on this iteration
    do {
      threshold *= 0.5;
      quantile = stats(distances).quantile(threshold);
      console.log("comparing " + initialQuantile + " to " + quantile);
      if (threshold < 0.4) {
        console.log("  knocking threshold to " + threshold);
      }
    } while (initialQuantile < quantile);
    threshold *= 2; // stupid hack to prepare for next do/whle

    // initialize and run the loop
    var clusters = [];
    do {
      threshold = threshold * 0.5;
      quantile = stats(distances).quantile(threshold);
      console.log("Clustering " + n + " fonts at threshold=" + threshold + " (" + quantile + ")");
      clusters = getClusters(inputArray, quantile);
    } while (clusters.length == 1 && threshold > 0.025);

    if (clusters.length == 1) return clusters; // no proceeeding from here

    clusters = deDuplicate(clusters);

    // if clusters have more than 5 members, recurse down
    for (var i = 0; i < clusters.length; ++i) {
      if (clusters[i].length > 5) {
        console.log(" recursing with quantile = " + quantile);
        clusters[i] = multiCluster(clusters[i], quantile);
      }
    }
    return clusters;
  }

  var initialQuantile = stats(getDistances(inputFontArray)).quantile(0.8);
  return multiClusterHelper(inputFontArray, initialQuantile);
}


var hierarchy = multiCluster(fontNames);
var asString = JSON.stringify(hierarchy, null, 2);
console.log(asString);

fs.writeFileSync(outputFilename, asString);
