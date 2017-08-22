"""Utilities to deal with BPZ pdz file ops."""


import sys
import re
import numpy as np
import astropy.io.fits as pyfits
from . import ldac


class PDZManager(object):

    def __init__(self, pdzcat):

        self.pdzcat = pdzcat
        self.pdzrange = None
        self.index = None

        self._buildPDZRange()
        self._buildIndex()

    def __getitem__(self, key):
        """
        Get an item value.

        key is the object ID
        returns pdz array
        index maps ID to element number
        """
        if self.index is None or key not in self.index:
            raise IndexError

        return self.pdzcat[self.index[key]][1]

    def _buildIndex(self):

        self.index = {}
        for i, iid in enumerate(self.pdzcat['SeqNr']):
            self.index[iid] = i

    def _buildPDZRange(self):

        self.pdzrange = np.arange(self.pdzcat.hdu.header['MINPDZ'],
                                  self.pdzcat.hdu.header['MAXPDZ'],
                                  self.pdzcat.hdu.header['PDZSTEP'])

    def save(self, outf):

        self.pdzcat.saveas(outf, clobber=True)

    def associatePDZ(self, z_ids):

        arrangedPDZ = []
        for cid in z_ids:
            arrangedPDZ.append(self[cid])

        finalPDZs = np.column_stack(arrangedPDZ).transpose()

        return self.pdzrange, finalPDZs

    @classmethod
    def parsePDZ(cls, pdzfile):
        """parses text output from BPZ."""

        inputf = open(pdzfile)

        headerline = inputf.readline()
        match = re.search(r'z=arange\((.+)\)', headerline)
        assert match is not None
        minPDZ, maxPDZ, pdzstep = map(float, match.group(1).split(','))

        ids = []
        pdzs = []
        for line in inputf.readlines():
            if re.match('^#', line):
                continue
            tokens = line.split()
            cid = int(tokens[0])
            pdz = map(float, tokens[1:])

            ids.append(cid)
            pdzs.append(pdz)

        npdzs = len(np.arange(minPDZ, maxPDZ, pdzstep))

        cols = [pyfits.Column(name='SeqNr', format='J', array=np.array(ids)),
                pyfits.Column(name='pdz', format='%dE' % npdzs, array=np.array(pdzs))]

        pdzs = ldac.LDACCat(
            pyfits.BinTableHDU.from_columns(pyfits.ColDefs(cols)))

        pdzs.hdu.header.update('MINPDZ', minPDZ)
        pdzs.hdu.header.update('MAXPDZ', maxPDZ)
        pdzs.hdu.header.update('PDZSTEP', pdzstep)

        return cls(pdzs)

    @classmethod
    def open(cls, pdzfile, table='OBJECTS'):
        """opens a pdzfile saved by PDZManager."""

        pdz = ldac.openObjectFile(pdzfile, table)

        return cls(pdz)


def parseRawPDZ(infile, outfile):

    pdzmanager = PDZManager.parsePDZ(infile)
    pdzmanager.save(outfile)


def createPDZcat(seqnr, pdzrange, pdz):

    npdzs = len(pdzrange)
    minPDZ = np.min(pdzrange)
    pdzstep = pdzrange[1] - pdzrange[0]
    maxPDZ = np.max(pdzrange) + pdzstep
    assert (np.arange(minPDZ, maxPDZ, pdzstep) == pdzrange).all()

    cols = [pyfits.Column(name='SeqNr', format='J', array=seqnr),
            pyfits.Column(name='pdz', format='%dE' % npdzs, array=pdz)]

    pdzs = ldac.LDACCat(pyfits.BinTableHDU.from_columns(pyfits.ColDefs(cols)))

    pdzs.hdu.header.update('MINPDZ', minPDZ)
    pdzs.hdu.header.update('MAXPDZ', maxPDZ)
    pdzs.hdu.header.update('PDZSTEP', pdzstep)

    return pdzs


if __name__ == '__main__':

    infile = sys.argv[1]
    outfile = sys.argv[2]

    parseRawPDZ(infile, outfile)
