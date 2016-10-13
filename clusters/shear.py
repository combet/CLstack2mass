"""Shear analysis."""

import numpy
import pylab
import seaborn
from astropy.table import Column
from . import data as cdata

def compute_shear(e1, e2, distx, disty):
    """Compute the shear."""
    phi = numpy.arctan2(disty, distx)
    gamt = - (e1 * numpy.cos(2.0 * phi) + e2 * numpy.cos(2.0 * phi))
    gamc = - e1 * numpy.sin(2.0 * phi) + e2 * numpy.cos(2.0 * phi)
    dist = numpy.sqrt(distx**2 + disty**2)
    return gamt, gamc, dist


def analysis(table, xclust, yclust):
    """Computethe shear.

    :param string data_file: Name of the hdf5 file to load
    :param string path: Path (key) of the table to load
    :return: A dictionnary containing the following keys and values:

     - meas: the 'deepCoadd_meas' catalog (an astropy table)
     - forced: the 'deepCoad_forced_src' catalog (an astropy table)
     - wcs: the 'wcs' of these catalogs (an ``astropy.wcs.WCS`` object)
    """
    e1r = table["ext_shapeHSM_HsmShapeRegauss_e1"][table['filter'] == 'r']
    e2r = table["ext_shapeHSM_HsmShapeRegauss_e2"][table['filter'] == 'r']
    e1i = table["ext_shapeHSM_HsmShapeRegauss_e1"][table['filter'] == 'i']
    e2i = table["ext_shapeHSM_HsmShapeRegauss_e2"][table['filter'] == 'i']
    distx = table["x_Src"][table['filter'] == 'r'] - xclust
    disty = table["y_Src"][table['filter'] == 'r'] - yclust

    # Quality cuts
    # magnitude cut
    filt = table['modelfit_CModel_mag'][table['filter'] == 'r'] < 23.5
    # resolution cut
    filt &= table['ext_shapeHSM_HsmShapeRegauss_resolution'][table['filter'] == 'i'] > 0.4
    # ellipticity cut
    filt &= (abs(e1i) < 1) & (abs(e2i) < 1)
    # er ~= ei
    filt &= (abs(e1r - e1i) < 0.5) & (abs(e2r - e2i) < 0.5)

    # Apply cuts
    e1i, e2i, distx, disty = [x[filt] for x in [e1i, e2i, distx, disty]]

    # Comput the shear
    gamt, gamc, dist = compute_shear(e1i, e2i, distx, disty)

    # Make some plots
    plot_shear(gamt, gamc, dist)


def xy_clust(config, wcs):
    return cdata.skycoord_to_pixel([config['ra'], config['dec']], wcs)
        
def compare_shear(forced_src, deepCoadd_meas, xclust, yclust):
    """Compare shear mesured on the coadd and shear measured on indivial ccd."""

    # Compute shear and distance for all srouces in both catalogs
    # And add that info into the tables
    tables = []
    for cat in [forced_src, deepCoadd_meas]:
        if 'objectId' in cat:
            objectids = cat["objectId"][cat['filter'] == 'i']
        else:
            objectids = cat["id"][cat['filter'] == 'i']
        e1i = cat["ext_shapeHSM_HsmShapeRegauss_e1"][cat['filter'] == 'i']
        e2i = cat["ext_shapeHSM_HsmShapeRegauss_e2"][cat['filter'] == 'i']
        distx = cat["x_Src"][cat['filter'] == 'i'] - xclust
        disty = cat["y_Src"][cat['filter'] == 'i'] - yclust

        tshear, cshear, dist = compute_shear(e1i, e2i, distx, disty)

        tables.append(Table([Column(name='Tshear', data=tshear, description='Tangential shear'),
                             Column(name='Cshear', data=cshear, description='Cross shear'),
                             Column(name='Distance', data=dist, description='Distance to center'),
                             Column(name='objectId', data=objectids, description='Object ID')]))
        return tables


def plot_shear(gamt, gamc, dist, drange=(0, 8500), nbins=8):
    """Plot shear."""
    dval, step = numpy.linspace(drange[0], drange[1], nbins, retstep=True)

    plot_hist([gamt, gamc], ['Gamt', 'Gamc'])
    plot_hist([gamt, gamc], ['Gamt', 'Gamc'], nbins=80, xarange=(-0.2, 0.2))

    plot_scatter([dist, dist], [gamt, gamc],
                 ['Dist', 'Dist'], ['Gamt', 'Gamc'], yarange=(-1, 1))

    masks = [(dist > d - step / 2) & (dist <= d + step / 2) for d in dval]
    tshear = [numpy.mean(gamt[mask]) for mask in masks]
    cshear = [numpy.mean(gamc[mask]) for mask in masks]
    tsheare = [numpy.std(gamt[mask]) / numpy.sqrt(len(gamt[mask])) for mask in masks]
    csheare = [numpy.std(gamc[mask]) / numpy.sqrt(len(gamc[mask])) for mask in masks]

    plot_scatter([dval, dval], [tshear, cshear],
                 ['Distance to cluster center (px)', 'Distance to cluster center (px)'],
                 ['Tangential shear', 'Cross shear'], yerrs=[tsheare, csheare],
                 xarange=(-500, 9000), yarange=(-0.06, 0.08))

    pylab.show()


def plot_hist(xs, labels, nbins=200, xarange=(-2, 2)):
    """Plot multiple histograms in subplots."""
    fig = pylab.figure(figsize=(15, 8))
    for i, x in enumerate(xs):
        ax = fig.add_subplot(1, len(xs), i + 1, xlabel=labels[i])
        ax.hist(x, bins=nbins, range=xarange)


def plot_scatter(xs, ys, xlabels, ylabels, **kwargs):
    """Plot multiple scatter plots in subplots.

    :param list xs: List of arrays for x axis
    :param list ys: List of arrays for y axis
    :param str xlabels: List of x labels
    :param str ylabels: List of y labels

    List of available kwargs:
    :param list yerrs: List of arrays, error on the y axis
    :param list xarange: Range for x axis (min,max)
    :param list yarange: Range for y axis (min,max)
    """
    fig = pylab.figure(figsize=(15, 8))
    for i, x in enumerate(xs):
        ax = fig.add_subplot(1, len(xs), i + 1, xlabel=xlabels[i], ylabel=ylabels[i])
        ax.axhline(0, color='k', ls=':')
        ax.scatter(x, ys[i], s=1, color='b')
        if 'yerrs' in kwargs:
            ax.errorbar(x, ys[i], yerr=kwargs['yerrs'][i])
        if 'xarange' in kwargs:
            ax.set_xlim(kwargs['xarange'])
        if 'xarange' in kwargs:
            ax.set_ylim(kwargs['yarange'])

