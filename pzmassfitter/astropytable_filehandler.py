""" 
File handler for an astropy table file format. 
Assumes that all relevant cuts have been applied to the file already.
"""


from __future__ import print_function
import numpy as np
import astropy.io.fits as pyfits
from astropy import coordinates as coord
from astropy import units as u
from . import util
from . import nfwutils
from . import ldac

class AstropyTableFilehandler(object):

    def __init__(self):

        self.cuts = []

    def addCLOps(self, parser):
        # not designed to be run from the command line

        raise NotImplementedError

    def createOptions(self, cluster, zcluster,
                      cat, mconfig,
                      cluster_ra,
                      cluster_dec,
                      raCol='coord_ra_deg',
                      decCol='coord_dec_deg',
                      g1Col='ext_shapeHSM_HsmShapeRegauss_e1',
                      g2Col='ext_shapeHSM_HsmShapeRegauss_e2',
                      sizeCol='rh',
                      snratioCol='snratio_scaled1',
                      wtg_shearcal=False,
                      psfsize=None,
#                      logprior=False,
                      options=None, args=None):

        if options is None:
            options = util.VarContainer()

        options.cluster = cluster
        options.zcluster = zcluster
        options.cluster_ra = cluster_ra
        options.cluster_dec = cluster_dec
        options.wtg_shearcal = wtg_shearcal
#        options.logprior = logprior

        if wtg_shearcal:
            options.psfsize = psfsize
            options.sizeCol = sizeCol
            options.snratioCol = snratioCol

        options.cat = cat
        options.mconfig = mconfig

        options.raCol = raCol
        options.decCol = decCol
        options.g1Col = g1Col
        options.g2Col = g2Col

        return options, args

    def readData(self, manager):

        options = manager.options

        manager.lensingcat = options.cat['deepCoadd_meas']
        manager.zcat = options.cat[options.mconfig['zconfig']]

        manager.clustername = options.cluster
        manager.zcluster = options.zcluster

        manager.logprior = options.logprior
        manager.wtg_shearcal = options.wtg_shearcal

        # Filter arrays
        # 1. only keep 'i' filter
        if 'filter' in manager.lensingcat.keys():
            manager.replace(
                'lensingcat', manager.lensingcat[manager.lensingcat["filter"] == 'i'])

        # 2. match galaxies in lensing cat, redshift cat and flag cat
        if 'objectId' in manager.zcat.keys():
            manager.matched_zcat = util.matchById(manager.zcat, manager.lensingcat, 'id', 'objectId' )
        else:
            manager.matched_zcat = util.matchById(manager.zcat, manager.lensingcat, 'id', 'id')


        # area normalized, ie density function
        manager.pz = manager.matched_zcat['pdz']
        z_b = manager.matched_zcat['Z_BEST']
            
        # 3. all objects have same zbins, take the first one
        manager.pdzrange = manager.zcat['zbins'][0]
        manager.replace('pdzrange', lambda: manager.pdzrange)

        # 4. only keep background galaxies in lensing cat and redshift cat
        if 'flag_' + options.mconfig['zconfig'] in options.cat.keys():

            manager.flagcat = options.cat['flag_'+options.mconfig['zconfig']]
            if 'objectId' in manager.flagcat.keys():
                manager.matched_flagcat = util.matchById(manager.flagcat, manager.lensingcat, 'id', 'objectId' )
            else:
                manager.matched_flagcat = util.matchById(manager.flagcat, manager.lensingcat, 'id', 'id')

            if 'zflagconfig' in options.mconfig:
                
                bck_gal = manager.matched_flagcat['flag_z_'+options.mconfig['zflagconfig']]
                print("Using "+ options.mconfig['zflagconfig']+" flag:", sum(bck_gal), ' remaining galaxies')

                
 #               manager.replace('lensingcat',
 #                               manager.lensingcat[options.cat["flag_" + options.mconfig['zconfig']]['flag_z_'+options.mconfig['zflagconfig']] == True])
 #               manager.replace('zcat',
 #                               manager.zcat[options.cat["flag_" + options.mconfig['zconfig']]['flag_z_'+options.mconfig['zflagconfig']] == True])

                manager.replace('lensingcat', manager.lensingcat[bck_gal])
                manager.replace('pz',  manager.pz[bck_gal])
                z_b = z_b[bck_gal]

        r_arcmin, E, B = compute_shear(cat=manager.lensingcat,
                                       center=(options.cluster_ra,
                                               options.cluster_dec),
                                       raCol=options.raCol,
                                       decCol=options.decCol,
                                       g1Col=options.g1Col,
                                       g2Col=options.g2Col)

        r_mpc = r_arcmin * (1. / 60.) * (np.pi / 180.) * \
            nfwutils.global_cosmology.angulardist(options.zcluster)

        if options.wtg_shearcal:
            manager.psfsize = options.psfsize
            size = manager.lensingcat[options.sizeCol] / options.psfsize
            snratio = manager.lensingcat[options.snratioCol]

 
        if manager.wtg_shearcal:
            cols = [pyfits.Column(name='SeqNr', format='J', array=manager.lensingcat['id']),
                    pyfits.Column(name='r_mpc', format='E', array=r_mpc),
                    pyfits.Column(name='size', format='E', array=size),
                    pyfits.Column(name='snratio', format='E', array=snratio),
                    pyfits.Column(name='z_b', format='E', array=z_b),
                    pyfits.Column(name='ghats', format='E', array=E),
                    pyfits.Column(name='B', format='E', array=B)]
        else:
            cols = [pyfits.Column(name='SeqNr', format='J', array=manager.lensingcat['id']),
                    pyfits.Column(name='r_mpc', format='E', array=r_mpc),
                    pyfits.Column(name='z_b', format='E', array=z_b),
                    pyfits.Column(name='ghats', format='E', array=E),
                    pyfits.Column(name='B', format='E', array=B)]

        manager.store('inputcat',
                      ldac.LDACCat(pyfits.BinTableHDU.from_columns(pyfits.ColDefs(cols))))

def compute_shear(cat, center, raCol, decCol, g1Col, g2Col):
    """Compute the radial and tangential shear."""
    cluster_ra, cluster_dec = center
    ra = cat[raCol]
    dec = cat[decCol]
    e1 = cat[g1Col]
    e2 = cat[g2Col]

#    posangle = (np.pi / 2.) - sphereGeometry.positionAngle(ra, dec, cluster_ra, cluster_dec)

#    Given this implementation, we need a minus sign to get the right position angle from ra, dec.
#    posangle = -((np.pi / 2.) - sphereGeometry.positionAngle(ra,
#                                                             dec, cluster_ra, cluster_dec))
#    r_arcmin = sphereGeometry.greatCircleDistance(
#        ra, dec, cluster_ra, cluster_dec) * 60

#   Using standard astropy coordinates rather than sphereGeometry.
#   sphereGeometry.posangle --> returns angle on [-pi, pi]
#   astropy.coordinates.position_angle [0, 2pi]
#   sphereGeometry.posangle = astropy.coordinates.position_angle if astropy.coordinates.position_angle < pi
#   sphereGeometry.posangle = astropy.coordinates.position_angle - 2pi otherwise
#   These angles are only unsed in cos(2phi) and sin(2phi), so that the difference above does not matter

    coord_cl = coord.SkyCoord(cluster_ra * u.deg, cluster_dec * u.deg)
#    coord_gal = coord.SkyCoord(ra * u.deg, dec * u.deg)
    coord_gal = coord.SkyCoord(ra, dec)

    posangle = -((np.pi / 2.) - coord_gal.position_angle(coord_cl).rad)

    r_arcmin = coord_gal.separation(coord_cl).arcmin

    cos2phi = np.cos(2 * posangle)
    sin2phi = np.sin(2 * posangle)

    E = -(e1 * cos2phi + e2 * sin2phi)
    B = e1 * sin2phi - e2 * cos2phi

    return r_arcmin, E, B
