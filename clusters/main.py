"""Main entry points for scripts."""

import os
import yaml
import sys
import cPickle
from argparse import ArgumentParser

from astropy.table import Table, hstack

from . import data as cdata
from . import extinction as cextinction
from . import zphot as czphot


def load_data(argv=None):
    """Load data from the DM stack butler."""
    description = """Load data from the DM stack butler."""
    prog = "clusters_data.py"
    usage = """%s [options] config""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument("--output",
                        help="Name of the output file (pkl file)")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    args = parser.parse_args(argv)

    config = cdata.load_config(args.config)

    if args.output is None:
        output = os.path.basename(args.config).replace('.yaml', '_data.hdf5')
        output_filtered = os.path.basename(args.config).replace('.yaml', '_filtered_data.hdf5')
    else:
        output = args.output
        output_filtered = "filtered_" + args.output

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'],
                                                    config['redshift'])
    print "INFO: Working on filters", config['filters']
    print "INFO: Butler located under %s" % config['butler']

    data = cdata.get_all_data(config['butler'], config['patches'],
                              config['filters'], add_extra=True)
    dataf = cdata.filter_table(data)
    cdata.write_data(data, output, overwrite=args.overwrite)
    cdata.write_data(dataf, output_filtered, overwrite=args.overwrite)


def extinction(argv=None):
    """Get color excess E(B-V) and store it in the data table for further use."""
    description = """Get color excess E(B-V) and store it in the data table for further use."""
    prog = "clusters_extinction.py"
    usage = """%s [options] config input""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument('input', help='Input data file: output of clusters_data.py, i.e, hdf5 file')
    parser.add_argument("--output",
                        help="Name of the output file (pkl file)")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    parser.add_argument("--plot", action='store_true', default=False,
                        help="Make some plots")
    args = parser.parse_args(argv)

    config = cdata.load_config(args.config)
    if args.output is None:
        args.output = os.path.basename(args.input).replace('.hdf5', '_extinction.hdf5')

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'], config['redshift'])
    print "INFO: Working on filters", config['filters']

    # Load the data
    data = cdata.read_data(args.input)['forced']

    # Query for E(b-v) and compute the extinction
    ebmv = {'ebv_sfd': cextinction.query(data['coord_ra_deg'],
                                         data['coord_dec_deg'],
                                         coordsys='equ', mode='sfd')['EBV_SFD']}
    albds = {}
    for k in ebmv:
        albd = cextinction.from_ebv_sfd_to_megacam_albd(ebmv[k])
        albds.update({k.replace('ebv_', 'albd_%s_' % f): albd[f] for f in albd})

    # Create a new table and save it
    new_tab = hstack([data['objectId', 'coord_ra', 'coord_dec', 'filter'],
                      Table(ebmv), Table(albds)], join_type='inner')
    new_tab.write(args.output, path='extinction', compression=True,
                  serialize_meta=True, overwrite=args.overwrite)
    print "INFO: Milky Way dust extinction correctino applied"
    print "INFO: Data saved in", args.output

    # Make some plots if asked
    if args.plot:
        print "INFO: Making some plots"
        filt = new_tab['filter'] == config['filters'][0]
        cextinction.plots(new_tab['coord_ra'][filt],
                          new_tab['coord_dec'][filt],
                          new_tab['ebv_sfd'], albds['albd_sfd'][filt],
                          filters=['u', 'g', 'r', 'i_old', 'i_new', 'z'],
                          title='Dust extinction map, %s, %i sources' %
                          (config['cluster'], len(new_tab['coord_ra'][filt])),
                          figname=config['cluster'])


def doplot(data, config, args):
    """Make a few plots."""
    print "INFO: Making some plots"
    data.hist('Z_BEST', min=0, nbins=100, xlabel='Photometric redshift',
              figname=config['cluster'],
              title="LEPHARE photo-z for %s (%i sources)" %
              (config['cluster'], data.nsources), zclust=config['redshift'])
    data.hist('CHI_BEST', nbins=100, max=100, figname=config['cluster'],
              title="LEPHARE photo-z for %s (%i sources)" %
              (config['cluster'], data.nsources))
    data.plot('CHI_BEST', 'Z_BEST', miny=0, figname=config['cluster'])
    data.plot_map(title="LEPHARE photometric redshift map for %s (%i sources)" %
                  (config['cluster'], data.nsources), figname=config['cluster'],
                  zmin=args.zmin, zmax=args.zmax)
    czphot.P.show()


def photometric_redshift(argv=None):
    """Comput photometric redshift using LEPHARE."""
    description = """Comput photometric redshift using LEPHARE."""
    prog = "clusters_zphot.py"
    usage = """%s [options] config input""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument('input', help='Input data file')
    parser.add_argument("--output",
                        help="Name of the output file (pkl file)")
    parser.add_argument("--data",
                        help="LEPHARE output file, used for the plots")
    parser.add_argument("--zpara",
                        help="LEPHARE configuration file (zphot.para)")
    parser.add_argument("--plot", action='store_true', default=False,
                        help="Make some plots")
    parser.add_argument("--zmin", type=float, default=0,
                        help="Redshift cut used to plot the map (min value)")
    parser.add_argument("--zmax", type=float, default=999,
                        help="Redshift cut used to plot the map (max value)")
    args = parser.parse_args(argv)

    config = yaml.load(open(args.config))
    if args.output is None:
        args.output = os.path.basename(args.config).replace('.yaml',
                                                            '_lephare_output.pkl')

    filters = config['filters']

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'],
                                                    config['redshift'])
    print "INFO: Working on filters", filters

    if args.data is not None:
        doplot(czphot.LEPHARO(args.data, args.data.replace('out', 'all')),
               config, args)
        sys.exit()

    # And dump them into a file
    data = cPickle.load(open(args.input, 'r'))
    mags, mags_sigma, coords = data[0], data[1], data[6]

    zp = czphot.LEPHARE(czphot.dict_to_array(mags, filters=filters),
                        czphot.dict_to_array(mags_sigma, filters=filters),
                        config['cluster'], filters=filters, zpara=args.zpara,
                        RA=coords['ra'], DEC=coords['dec'], ID=coords['id'])
    zp.check_config()
    zp.run()

    cPickle.dump(zp.data_out.data_dict, open(args.output, 'w'))
    print "INFO: LEPHARE data saved in", args.output

    if args.plot:
        doplot(zp.data_out, config, args)


def get_background(argv=None):
    """Get a cluster background galaxies."""
    description = """Get a cluster background galaxies."""
    prog = "clusters_getbackground.py"
    usage = """%s [options] config input""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument('input', help='Input data file')
    args = parser.parse_args(argv)

    config = yaml.load(open(args.config))
    if args.output is None:
        args.output = os.path.basename(args.config).replace('.yaml',
                                                            '_getbck_output.pkl')

    filters = config['filters']

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'],
                                                    config['redshift'])
    print "INFO: Working on filters", filters
    print "WARNING: Implementation not finished for this part of the analysis."
    print "EXIT."
