#!/bin/bash -xe
#
# A script to setup the Travis build environment with Miniconda
# and install the LSST stack into it.

MINICONDA_VERSION=${MINICONDA_VERSION:-"latest"}
CHANNEL=${CHANNEL:-"http://conda.lsst.codes/stack"} 
CACHE_DIR="$HOME/miniconda.tarball"
CACHE_DIR_TMP="$CACHE_DIR.tmp"
CACHE_TARBALL_NAME="miniconda.tar.gz"
CACHE_TARBALL_PATH="$CACHE_DIR/$CACHE_TARBALL_NAME"
PACKAGES="gcc lsst-daf-persistence lsst-log lsst-afw lsst-skypix lsst-meas-algorithms lsst-pipe-tasks"

# Store a record of what's in the cached tarball
# This record allows us to automatically regenerate the tarball if the installed packages change.
rm -f "$HOME/info.txt"
cat > "$HOME/info.txt" <<-EOT
	# -- cache information; autogenerated by ci/install.sh
	MINICONDA_VERSION=$MINICONDA_VERSION
	CHANNEL=$CHANNEL
	PACKAGES=$PACKAGES
EOT
cat "$HOME/info.txt"

if [ -f "$CACHE_TARBALL_PATH" ] && cmp "$HOME/info.txt" "$CACHE_DIR/info.txt"; then
 # Restore from cached tarball
 tar xzf "$CACHE_TARBALL_PATH" -C "$HOME"
 ls -l "$HOME"
 source activate lsst
else
 # Miniconda install
 # Install Python 2.7 Miniconda
 wget https://repo.continuum.io/miniconda/Miniconda2-$MINICONDA_VERSION-Linux-x86_64.sh -O miniconda.sh
 bash miniconda.sh -b -p $HOME/miniconda
 export PATH="$HOME/miniconda/bin:$PATH"
 hash -r
 conda config --set always_yes yes --set changeps1 no
 conda update -q conda
 conda info -a

 # Stack install
 conda config --add channels "$CHANNEL"
 conda create -q -n lsst python=$TRAVIS_PYTHON_VERSION
 source activate lsst
 conda install -q $PACKAGES

 # Pack for caching. We pack here as Travis tends to time out if it can't pack
 # the whole directory in ~180 seconds.
 rm -rf "$CACHE_DIR" "$CACHE_DIR_TMP"
 mkdir "$CACHE_DIR_TMP"
 tar czf "$CACHE_DIR_TMP/$CACHE_TARBALL_NAME" -C "$HOME" miniconda
 mv "$HOME/info.txt" "$CACHE_DIR_TMP"
 mv "$CACHE_DIR_TMP" "$CACHE_DIR"	# Atomic rename
 ls -l "$CACHE_DIR"
fi

# Source
source eups-setups.sh
setup daf_persistence

# Install obs_cfht
git clone https://github.com/lsst/obs_cfht.git
cd obs_cfht
git checkout b7ab2c4
setup -k -r .
scons opt=3
eups declare -r . -t travis
cd ../
