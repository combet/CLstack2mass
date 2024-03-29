"""Main entry points for scripts."""


from __future__ import print_function
import os
import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from .. import data as cdata
from .. import utils as cutils


def load_data(argv=None):
    """Load data from the DM stack butler."""
    description = """Load data from the DM stack butler."""
    prog = "clusters_data.py"
    usage = """%s [options] config""" % prog

    parser = ArgumentParser(prog=prog, usage=usage, description=description,
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('config', help='Configuration (yaml) file')
    parser.add_argument("--output",
                        help="Name of the output file (hdf5 file)")
    parser.add_argument("--catalogs",
                        default='forced_src,deepCoadd_meas,deepCoadd_forced_src',
                        help="List of catalogs to load (coma separated)")
    parser.add_argument("--filter",
                        default=None,
                        help='Apply basic filters to an already loaded hdf5 file'
                        ', given as an input to this option.')
    parser.add_argument("--nofilter", action="store_true", default=False,
                        help="Do not apply filters on the data. Useful for simulated data.")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite the output files if they exist already")
    parser.add_argument("--show", action="store_true", default=False,
                        help="Show and save the list of available keys in the catalogs, and exit.")
    parser.add_argument("--MT", action="store_true", default=False,
                        help="Enables multithreading for loading the catalogs.")

    args = parser.parse_args(argv)

    config = cutils.load_config(args.config)

    if args.output is None:
        output = os.path.basename(args.config).replace('.yaml', '_data.hdf5')
        output_filtered = os.path.basename(
            args.config).replace('.yaml', '_filtered_data.hdf5')
    else:
        output = args.output if args.output.endswith(
            '.hdf5') else args.output + ".hdf5"
        output_filtered = output.replace('.hdf5', '_filtered_data.hdf5')

    if not args.overwrite and (os.path.exists(output) or os.path.exists(output_filtered)):
        raise IOError(
            "Output(s) already exist(s). Remove them or use overwrite=True.")

    print("\nINFO from config file:")
    if 'cluster' in config:
        print("  - cluster %s (z=%.4f)" %
              (config['cluster'], config['redshift']))
    if 'filter' in config:
        print("  - filters", config['filter'])
    if 'tract' in config:
        print("  - tracts", config['tract'])
    if 'patch' in config:
        print("  - patches", config['patch'])
    print("INFO: Butler located under %s" % config['butler'])

    # Apply filter and quit?
    if args.filter is not None:
        apply_filter(args.filter, config, output_filtered, args.overwrite)
        sys.exit()

#    data = cdata.Catalogs(config['butler'])
    data = cdata.DRPCatalogs(config['butler'])
    if args.show:
        data.show_keys(args.catalogs.split(','))
        return
    config['output_name'] = output
    config['overwrite'] = args.overwrite
    config['MT'] = args.MT
    data.load_catalogs(args.catalogs.split(','), matchid=True, **config)

    # Apply filter
    if not args.nofilter:
        apply_filter(output, config, output_filtered, args.overwrite)


def apply_filter(hdf5file, config, output, overwrite):
    """Apply quality cuts and only keep the galaxies."""
    print("\nINFO: Applying filters on the data to keep a clean sample of galaxies")
    catalogs = cutils.read_hdf5(hdf5file)
#    data = cdata.Catalogs(config['butler'], load_butler=False)
    data = cdata.DRPCatalogs(config['butler'])
    data.catalogs = cutils.filter_table(catalogs)
#    data.save_catalogs(output, overwrite=overwrite, delete_catalog=True)
    data.save_catalogs(output, overwrite=overwrite, delete_catalog=False)
