"""Main entry points for scripts."""

import os
import yaml
import sys
from argparse import ArgumentParser

from astropy.table import Table, hstack

from . import data as cdata
from . import extinction as cextinction
from . import zphot as czphot
from . import shear as cshear
from . import background


def load_data(argv=None):
    """Load data from the DM stack butler."""
    description = """Load data from the DM stack butler."""
    prog = "clusters_data.py"
    usage = """%s [options] config""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument("--output",
                        help="Name of the output file (hdf5 file)")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    parser.add_argument("--show", action="store_true", default=False,
                        help="Show and save the list of available keys in the catalogs, and exit.")
    args = parser.parse_args(argv)

    config = cdata.load_config(args.config)

    if args.output is None:
        output = os.path.basename(args.config).replace('.yaml', '_data.hdf5')
        output_filtered = os.path.basename(args.config).replace('.yaml', '_filtered_data.hdf5')
    else:
        output = args.output
        output_filtered = "filtered_" + args.output

    if not args.overwrite and (os.path.exists(output) or os.path.exists(output_filtered)):
        raise IOError("Output(s) already exist(s). Remove them or use overwrite=True.")

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'],
                                                    config['redshift'])
    print "INFO: Working on filters", config['filters']
    print "INFO: Butler located under %s" % config['butler']

    data = cdata.get_all_data(config['butler'], config['patches'],
                              config['filters'], add_extra=True, show=args.show,
                              keys=config['keys'] if 'keys' in config else None)
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
                        help="Name of the output file (hdf5 file)")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    parser.add_argument("--plot", action='store_true', default=False,
                        help="Make some plots")
    args = parser.parse_args(argv)

    config = cdata.load_config(args.config)
    if args.output is None:
        args.output = os.path.basename(args.input).replace('.hdf5', '_extinction.hdf5')
        if not args.overwrite and os.path.exists(args.output):
            raise IOError("Output already exists. Remove them or use --overwrite.")

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'], config['redshift'])
    print "INFO: Working on filters", config['filters']

    # Load the data
    data = cdata.read_data(args.input)['deepCoadd_forced_src']

    # Query for E(b-v) and compute the extinction
    ebmv = {'ebv_sfd': cextinction.query(data['coord_ra_deg'].tolist(),
                                         data['coord_dec_deg'].tolist(),
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
    print "INFO: Milky Way dust extinction correction applied"
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


def doplot(data, config, zmin=0, zmax=999):
    """Make a few plots."""
    print "INFO: Making some plots"
    data.hist('Z_BEST', minv=0, nbins=100, xlabel='Photometric_redshift',
              title="LEPHARE photo-z for %s (%i sources)" %
              (config['cluster'], data.nsources), zclust=config['redshift'])
    data.hist('CHI_BEST', nbins=100, maxv=100,
              title="LEPHARE photo-z for %s (%i sources)" % (config['cluster'], data.nsources))
    data.plot('CHI_BEST', 'Z_BEST', miny=0)
    data.plot_map(title="LEPHARE photometric redshift map for %s (%i sources)" %
                  (config['cluster'], data.nsources), zmin=zmin, zmax=zmax)


def photometric_redshift(argv=None):
    """Comput photometric redshift using LEPHARE."""
    info = {}
    info['description'] = """Comput photometric redshift using LEPHARE."""
    info['prog'] = "clusters_zphot.py"
    info['usage'] = """%s [options] config input""" % info['prog']

    parser = ArgumentParser(prog=info['prog'], usage=info['usage'], description=info['description'])
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument('input', help='Input data file')
    parser.add_argument("--output",
                        help="Name of the output file (hdf5 file)")
    parser.add_argument("--extinction",
                        help="Output of clusters_extinction (hdf5 file)."
                        "Use to compute the extinction-corrected magnitudes.")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    parser.add_argument("--zpara",
                        help="Comma-separated LEPHARE configuration files (zphot.para)")
    parser.add_argument("--plot", action='store_true', default=False,
                        help="Make some plots")
    parser.add_argument("--zrange", default="0,999",
                        help="Redshift range used to plot the map (min,max)")
    parser.add_argument("--mag", type=str, default='modelfit_CModel_mag',
                        help="Magnitude name [default]")
    parser.add_argument("--data",
                        help="LEPHARE output file, used for the analysis only (plots)")
    args = parser.parse_args(argv)

    config = cdata.load_config(args.config)
    if args.data is not None:
        doplot(czphot.LEPHARO(args.data, args.data.replace('_zphot', '')),
               config, float(args.zrange.split(',')[0]), float(args.zrange.split(',')[1]))
        sys.exit()

    if args.output is None:
        args.output = os.path.basename(args.input).replace('.hdf5', '_zphot.hdf5')
        if not args.overwrite and os.path.exists(args.output):
            raise IOError("Output already exists. Remove themit or use --overwrite.")

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'], config['redshift'])
    print "INFO: Working on filters", config['filters']

    # Load the data
    print "INFO: Loading the data from", args.input
    data = cdata.read_data(args.input)['deepCoadd_forced_src']

    mag = args.mag
    # Compute extinction-corrected magitudes
    if args.extinction is not None:
        print "INFO: Computing extinction-corrected magnitude for", args.mag
        edata = cdata.read_data(args.extinction, path='extinction')
        cdata.correct_for_extinction(data, edata, mag=args.mag)
        mag += "_extcorr"

    # Make sure the selected magnitude does exist in the data table
    if mag not in data.keys():
        raise IOError("%s is not a column of the input table" % mag)

    # Run LEPHARE
    print "INFO: LEPHARE will run on", len(data) / len(config['filters']), "sources"

    if args.zpara is None:
        args.zpara = os.environ["LEPHAREDIR"] + \
                     "/config/zphot_megacam.para" if 'zpara' not in config else config['zpara']

    for i, zpara in enumerate(args.zpara.split(',') if isinstance(args.zpara, str) else args.zpara):
        print "\nINFO: Configuration for LEPHARE from:", zpara
        kwargs = {'basename': config['cluster'] + '_' + zpara.split('/')[-1].replace('.para', ''),
                  'filters': config['filters'],
                  'ra': data['coord_ra_deg'][data['filter'] == config['filters'][0]],
                  'dec': data['coord_dec_deg'][data['filter'] == config['filters'][0]],
                  'id': data['objectId'][data['filter'] == config['filters'][0]]}
        zphot = czphot.LEPHARE([data[mag][data['filter'] == f] for f in config['filters']],
                               [data[args.mag + "Sigma"][data['filter'] == f]
                                for f in config['filters']],
                               zpara=zpara, **kwargs)
        zphot.check_config()
        zphot.run()

        # Create a new table and save it
        path = "zphot_%s" % zpara.split('/')[-1].replace('.para', '')
        new_tab = hstack([data['objectId',
                               'coord_ra_deg',
                               'coord_dec_deg'][data['filter'] == config['filters'][0]],
                          Table(zphot.data_out.data_dict)], join_type='inner')
        if i == 0:
            new_tab.write(args.output, path=path, compression=True,
                          serialize_meta=True, overwrite=args.overwrite)
        else:
            new_tab.write(args.output, path=path, compression=True,
                          serialize_meta=True, append=True)
        print "INFO: LEPHARE data saved in", args.output, "as", path

        if args.plot:
            doplot(zphot.data_out, config,
                   float(args.zrange.split(',')[0]),
                   float(args.zrange.split(',')[1]))

    if args.plot:
        czphot.P.show()


def getbackground(argv=None):
    """Get a cluster background galaxies."""
    description = """Get a cluster background galaxies."""
    prog = "clusters_getbackground.py"
    usage = """%s [options] config input""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument('input', help='Input data file')
    parser.add_argument("--output",
                        help="Name of the output file (hdf5 file)")
    args = parser.parse_args(argv)

    config = yaml.load(open(args.config))
    if args.output is None:
        args.output = os.path.basename(args.config).replace('.yaml',
                                                            '_background.hdf5')

    filters = config['filters']

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'],
                                                    config['redshift'])
    print "INFO: Working on filters", filters

    data = cdata.read_data(args.input)
    background.get_background(config, data['deepCoadd_forced_src'])


def shear(argv=None):
    """Compute the shear."""
    description = """Compute the shear."""
    prog = "clusters_shear.py"
    usage = """%s [options] config input""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument('input', help='Input data file: output of clusters_data.py, i.e, hdf5 file')
    parser.add_argument("--output",
                        help="Name of the output file (hdf5 file)")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    parser.add_argument("--plot", action='store_true', default=False,
                        help="Make some plots")
    args = parser.parse_args(argv)

    config = cdata.load_config(args.config)
    if args.output is None:
        args.output = os.path.basename(args.input).replace('.hdf5', '_shear.hdf5')
        if not args.overwrite and os.path.exists(args.output):
            raise IOError("Output already exists. Remove them or use --overwrite.")

    print "INFO: Working on cluster %s (z=%.4f)" % (config['cluster'], config['redshift'])
    print "INFO: Working on filters", config['filters']

    # Load the data
    data = cdata.read_data(args.input)
    meas = data['deepCoadd_meas']
    wcs = data['wcs']
    xclust, yclust = cdata.skycoord_to_pixel([config['ra'], config['dec']], wcs)
    cshear.analysis(meas, float(xclust), float(yclust))


def pipeline(argv=None):
    """Pipeline for a standard cluster analysis."""
    description = """Run standard comand lines for full cluster analysis."""
    prog = "clusters_pipeline.py"
    usage = """%s [options] config""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument("--output",
                        help="Name of the output file (hdf5 file)")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    args = parser.parse_args(argv)

    load_data()
    extinction(argv=None)
    print "TBD", args.config
