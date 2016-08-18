"""Data builder and parser for the Clusters package."""

import yaml
import numpy as N
from astropy.table import Table, Column, vstack


def load_config(config):
    """Load the configuration file, and return the corresponding dictionnary.

    :param config: Name of the configuretion file.
    :type config: str.
    :returns: dic

    """
    return yaml.load(open(config))


def shorten(doc):
    """Hack to go around an astropy/hdf5 bug. Cut in half words longer than 18 chars."""
    return " ".join([w if len(w) < 18 else (w[:len(w) / 2] + ' - ' + w[len(w) / 2:])
                     for w in doc.split()])


def get_astropy_table(cat):
    """Convert an afw data table into a simple astropy table."""
    schema = cat.getSchema()
    dic = {n: cat.get(n) for n in schema.getNames()}
    tab = Table(dic)
    for k in schema.getNames():
        tab[k].description = shorten(schema[k].asField().getDoc())
        tab[k].unit = schema[k].asField().getUnits()
    return tab


def get_from_butler(butler, key, filt, patch, tract=0, table=False):
    """
    Return selected data from a butler for a given key, tract, patch and filter.

    Either retrun the object or the astropy table version of it
    """
    dataid = {'tract': tract, 'filter': filt, 'patch': patch}
    b = butler.get(key, dataId=dataid)
    return b if not table else get_astropy_table(b)


def add_magnitudes(t, getmagnitude):
    """Compute magns for all fluxes of a given table. Add the corresponding new columns."""
    kfluxes = [k for k in t.columns if k.endswith('_flux')]
    ksigmas = [k + 'Sigma' for k in kfluxes]
    for kf, ks in zip(kfluxes, ksigmas):
        m, dm = N.array([getmagnitude(f, s) for f, s in zip(t[kf], t[ks])]).T
        t.add_columns([Column(name=kf.replace('_flux', '_mag'), data=m,
                              description='Magnitude', unit='mag'),
                       Column(name=ks.replace('_fluxSigma', '_magSigma'), data=dm,
                              description='Magnitude error', unit='mag')])


def add_position(t, wcs_alt):
    """Compute the x/y position in pixel for all sources. Add new columns to the table."""
    x, y = N.array([wcs_alt(ra, dec) for ra, dec in zip(t["coord_ra"], t["coord_dec"])]).T
    t.add_columns([Column(name='x_Src', data=x,
                          description='x coordinate', unit='pixel'),
                   Column(name='y_Src', data=y,
                          description='y coordinate', unit='pixel')])


def add_filter_column(table, filt):
    """Add a new column containing the filter name."""
    table.add_column(Column(name='filter', data=[filt] * len(table), description='Filter name'))


def add_patch_column(table, patch):
    """Add a new column containing the patch name."""
    table.add_column(Column(name='patch', data=[patch] * len(table), description='Patch name'))


def add_extra_info(d):
    """Add magnitude and position to all tables."""
    # take the first filter, and the first patch
    f = d.keys()[0]
    p = d[f].keys()[0]

    # get the calib objects
    wcs = d[f][p]['calexp'].getWcs()

    import lsst.afw.geom as afwGeom
    def wcs_alt(r, d):
        """Redifine the WCS function."""
        return wcs.skyToPixel(afwGeom.geomLib.Angle(r), afwGeom.geomLib.Angle(d))

    getmag = d[f][p]['calexp'].getCalib().getMagnitude

    def mag(flux, sigma):
        """Redefine the magnitude function. Negative flux or sigma possible."""
        if flux <= 0 or sigma <= 0:
            return N.nan, N.nan
        else:
            return getmag(flux, sigma)

    # compute all magnitudes and positions
    for f in d:
        for p in d[f]:
            for e in ['meas', 'forced']:
                print "INFO: adding extra info for", f, p, e
                add_magnitudes(d[f][p][e], mag)
                add_filter_column(d[f][p][e], f)
                add_patch_column(d[f][p][e], p)
                add_position(d[f][p][e], wcs_alt)

    return d


def get_all_data(path, patches, filters, add_extra=False):
    """
    Get butler data for a list of patches and filters.

    Return a dictionnary with filters as keys
    """
    import lsst.daf.persistence as dafPersist
    print "INFO: Loading data from", path, " pathes:", patches, " filters:", filters
    butler = dafPersist.Butler(path)
    d = {f: get_filter_data(butler, patches, f) for f in filters}
    return stack_tables(d) if not add_extra else stack_tables(add_extra_info(d))


def get_filter_data(butler, patches, f):
    """
    Get butler data for a list of patches, for a given filter.

    Return a dictionnary with patches as keys
    """
    print "INFO: loading filter", f
    return {p: get_patch_data(butler, p, f) for p in patches}


def get_patch_data(butler, p, f):
    """Get bulter data for a given set of patch and filter."""
    print "INFO:   loading patch", p
    meas = get_from_butler(butler, 'deepCoadd_meas', f, p, table=True)
    forced = get_from_butler(butler, 'deepCoadd_forced_src', f, p, table=True)
    calexp = get_from_butler(butler, 'deepCoadd_calexp', f, p, table=False)
    return {'meas': meas, 'forced': forced, 'calexp': calexp}


def from_list_to_array(d):
    """Transform lists (of dict of list) into numpy arrays."""
    if type(d) in [list, N.ndarray]:
        return N.array(d)
    for k in d:
        if type(d[k]) == list:
            d[k] = N.array(d[k])
        elif type(d[k]) == dict:
            from_list_to_array(d[k])
    return d


def stack_tables(d):
    """
    Stack the astropy tables across all patches.

    Return a new dictionnary of the form:
    d = {u: {'forced': table, 'meas': table}, g: {'forced': table, 'meas': table}, ...}
    """
    print "Info: Stacking the data (patches, filters) into a single astropy table"
    return {'meas': vstack([vstack([d[f][p]['meas']
                                    for p in d[f]]) for f in d]),
            'forced': vstack([vstack([d[f][p]['forced']
                                      for p in d[f]]) for f in d])}


def write_data(d, output, overwrite=False):
    """Write astropy 'forced' and 'meas' tables in an hdf5 file."""
    d['forced'].write(output, path='forced', compression=True,
                      serialize_meta=True, overwrite=overwrite)
    d['meas'].write(output, path='meas', compression=True, append=True, serialize_meta=True)


def read_data(data_file, path=None):
    """Write astropy tables from an hdf5 file."""
    if path is None:
        try:
            return {'meas': Table.read(data_file, path='meas'),
                    'forced': Table.read(data_file, path='forced')}
        except:
            return Table.read(data_file)
    else:
        return Table.read(data_file, path=path)


def filter_table(t):
    """Apply a few quality filters on the data tables."""
    # Get the initial number of filter
    nfilt = len(t['meas'].group_by('id').groups[0])

    # Select galaxies (and reject stars)
    filt = t['meas']['base_ClassificationExtendedness_flag'] == 0  # keep galaxy
    filt &= t['meas']['base_ClassificationExtendedness_value'] >= 0.5  # keep galaxy

    # Gauss regulerarization flag
    filt &= t['meas']['ext_shapeHSM_HsmShapeRegauss_flag'] == 0

    # Make sure to nin pprimary sources
    filt &= t['meas']['detect_isPrimary'] == 1

    # Check the flux value, which must be > 0
    filt &= t['forced']['modelfit_CModel_flux'] > 0

    # Select sources which have a proper flux value
    filt &= t['forced']['modelfit_CModel_flag'] == 0

    # Check the signal to noise (stn) value, which must be > 10
    filt &= (t['forced']['modelfit_CModel_flux'] /
             t['forced']['modelfit_CModel_fluxSigma']) > 10

    # Only keeps sources with the 5 filters
    dmg = t['meas'][filt].group_by('id')
    dfg = t['forced'][filt].group_by('objectId')

    # Indices difference is a quick way to get the lenght of each group
    filt = (dmg.groups.indices[1:] - dmg.groups.indices[:-1]) == nfilt

    return {'meas': dmg.groups[filt], 'forced': dfg.groups[filt]}


def getdata(config, output='all_data.hdf5', output_filtered='filtered_data.hdf5', overwrite=False):
    """Shortuc function to get all the data from a bulter, fitler them, and save same."""
    if isinstance(config, str):
        config = load_config(config)
    d = get_all_data(config['butler'], config['patches'],
                     config['filters'], add_extra=True)
    write_data(d, output, overwrite=overwrite)
    df = filter_table(d)
    write_data(df, output_filtered, overwrite=overwrite)
    return d, df


def correct_for_extinction(ti, te, mag='modelfit_CModel_mag', ext='sfd', ifilt="i_new"):
    """
    Compute extinction-corrected magnitude.

    Inputs:
    - data table
    - extinction table
    - type of magnitude
    - type of extinction
    - ifilt is the 'i' filter you want to use (i_old or i_new)

    Return an astropy table compatible with the input one, with a new key added 'mag'+_extcorr.
    """
    filters = list(set(te['filter']))
    for i, f in enumerate(filters):
        if f == 'i':
            filters[i] = ifilt
    magext = mag + '_extcorr'
    mcorr = N.zeros(len(ti[mag]))
    for f in filters:
        filt = ti['filter'] == (f if 'i' not in f else 'i')
        mcorr[filt] = ti[mag][filt] - te['albd_%s_%s' % (f, ext)][filt]
    print len(mcorr), len(ti['filter'])
    ti.add_columns([Column(name=magext, data=mcorr, unit='mag',
                           description='Extinction corrected magnitude (i=%s, ext=%s)' %
                           (ifilt, ext))])
