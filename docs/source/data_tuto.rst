
.. note::
    The corresponding Jupyter notebook can be found `here <https://github.com/nicolaschotard/Clusters/blob/master/docs/source/data_tuto.ipynb>`_. You can also reproduce these results in `ipython <https://ipython.org/>`_.

``Astropy`` tables are great to work with, and can be used for all kind of
analysis in the context of our cluster study. You can apply filters,
group by column, concatenate them, etc. For a detailed review on
Astropy tables, see `there <http://docs.astropy.org/en/stable/table/>`_.

Load the table
~~~~~~~~~~~~~~

The ``Astropy`` tables created by the ``clusters_data`` step are saved
in an ``hdf5`` file, and contains two tables, corresponding to two
output catalogs of the data processing using the DM stack. As an
example, we will use here the ``forced`` catalog, corresponding to the
forced photometry processing (`some details
<https://confluence.lsstcorp.org/display/DM/S15+Multi-Band+Coadd+Processing+Prototype>`_).

If you want to start an analysis with an existing ``hdf5`` file containing catalogs, you can use the one we have created for MACSJ2243.3-0935, which is saved at CC-IN2P3 under::

  /sps/lsst/data/clusters/MACSJ2243.3-0935/analysis/output_v1/MACSJ2243.3-0935_data.hdf5

To load the ``forced`` catalog, do:

.. code:: python

    from Clusters import data
    f = "/sps/lsst/data/clusters/MACSJ2243.3-0935/analysis/output_v1/MACSJ2243.3-0935_data.hdf5"
    d = data.read_data(f)
    fc = d['forced']

``d`` is a dictionnary containing the 'forced' and 'meas' catalogs

.. code:: python

    print d.keys()


.. parsed-literal::

    ['forced', 'meas']


and ``fc`` is an astropy table

.. code:: python

    print fc


.. parsed-literal::

    base_CircularApertureFlux_70_0_flux ... coord_dec_deg 
                     ct                 ...      deg      
    ----------------------------------- ... --------------
                                    nan ... -9.50417299504
                                    nan ... -9.50631091083
                                    nan ... -9.50631273401
                                    nan ... -9.50632589495
                                    nan ...  -9.5063327395
                                    nan ...  -9.5062460577
                                    nan ... -9.50629874096
                                    nan ... -9.50635437897
                                    nan ... -9.50600120865
                                    nan ... -9.50549567214
                                    ... ...            ...
                          1.50556364615 ... -9.73333093082
                          3.38628042737 ... -9.73388006895
                          34.7225751682 ...  -9.7302761071
                          34.9437715002 ... -9.73010079525
                          33.6814404931 ... -9.72701283749
                          30.9058971442 ...  -9.7273114286
                         -57.1279619848 ... -9.91085559972
                          -8.0121195399 ... -9.91084514606
                         -7.38991968287 ...  -9.8851539436
                         -20.8298629206 ... -9.88578472829
    Length = 1050500 rows


As you can see, there are 

.. code:: python

    N = len(fc)
    print N, "rows"


.. parsed-literal::

    1050500 rows


in this table. This number correspond to the number of sources (ns) times the number of filters (nf): N = ns x nf. In this table, we have the following number of filter:

.. code:: python

    filters = set(fc['filter'])
    nf = len(filters)
    print nf, "filters:", filters 


.. parsed-literal::

    5 filters: set(['i', 'r', 'u', 'z', 'g'])


The number of sources in this catalog if thus:

.. code:: python

    ns = N / nf
    print ns, "sources"


.. parsed-literal::

    210100 sources


The number of columns corresponding to the number of keys available in the catalog is:

.. code:: python

    print "%i columns" % len(fc.keys())
    for k in sorted(fc.keys())[:10]:
        print k


.. parsed-literal::

    195 columns
    base_CircularApertureFlux_12_0_flag
    base_CircularApertureFlux_12_0_flag_apertureTruncated
    base_CircularApertureFlux_12_0_flux
    base_CircularApertureFlux_12_0_fluxSigma
    base_CircularApertureFlux_12_0_mag
    base_CircularApertureFlux_12_0_magSigma
    base_CircularApertureFlux_17_0_flag
    base_CircularApertureFlux_17_0_flag_apertureTruncated
    base_CircularApertureFlux_17_0_flux
    base_CircularApertureFlux_17_0_fluxSigma


Apply filters
~~~~~~~~~~~~~

You can filter this table to, for example, only keep the ``i`` and ``r`` magnitude of the ``modelfit_CModel_mag`` for all sources:

.. code:: python

    magi = fc['modelfit_CModel_mag'][fc['filter'] == 'i']
    magr = fc['modelfit_CModel_mag'][fc['filter'] == 'r']

and plot them against each other

.. code:: python

    %matplotlib inline
    import pylab
    pylab.scatter(magi, magr)
    pylab.xlabel('i mag')
    pylab.ylabel('r mag')
    pylab.title('%i sources (galaxies+stars)' % len(magi))




.. parsed-literal::

    <matplotlib.text.Text at 0x7fe09490fb50>




.. image:: data_tuto_files/data_tuto_17_1.png


A few standard filters have been implemented in ``data`` and can be used directly to get a clean sample of galaxies:  

.. code:: python

    # ignore these lines
    import warnings
    warnings.filterwarnings("ignore")
    # ignore these lines

.. code:: python

    data_filtered = data.filter_table(d)
    fc_filtered = data_filtered['forced']

The same plot as in the above example now looks like

.. code:: python

    magi_filtered = fc_filtered['modelfit_CModel_mag'][fc_filtered['filter'] == 'i']
    magr_filtered = fc_filtered['modelfit_CModel_mag'][fc_filtered['filter'] == 'r']
    pylab.scatter(magi_filtered, magr_filtered)
    pylab.xlabel('i mag')
    pylab.ylabel('r mag')
    pylab.title('%i sources (clean sample of galaxies)' % len(magi_filtered))




.. parsed-literal::

    <matplotlib.text.Text at 0x7fe0ee741350>




.. image:: data_tuto_files/data_tuto_22_1.png


See `the code <https://github.com/nicolaschotard/Clusters/blob/master/clusters/data.py#L207>`_ for a few other examples on how to use filters.

Add a new column
~~~~~~~~~~~~~~~~

You can also add a new column to the table (`examples here <https://github.com/nicolaschotard/Clusters/blob/master/clusters/data.py#L53>`_)

.. code:: python

    from astropy.table import Column

Create a simple shifted magnitude array

.. code:: python

    shifted_mags = fc_filtered['modelfit_CModel_mag'] + 2

Add it to the initial table and plot it against the initial magnitude (for the `i` filter here)

.. code:: python

    fc_filtered.add_column(Column(name='shifted_mag', data=shifted_mags,
                                  description='Shifted magnitude', unit='mag'))

.. code:: python

    magi_filtered = fc_filtered['modelfit_CModel_mag'][fc_filtered['filter'] == 'i']
    magi_shifted =  fc_filtered['shifted_mag'][fc_filtered['filter'] == 'i']
    pylab.scatter(magi_filtered, magi_filtered)
    pylab.scatter(magi_filtered, magi_shifted, c='r')
    pylab.xlabel('i mag')
    pylab.ylabel('shifted i mag')
    pylab.title('%i sources (clean sample of galaxies)' % len(magi_filtered))




.. parsed-literal::

    <matplotlib.text.Text at 0x7fe0eeaa52d0>




.. image:: data_tuto_files/data_tuto_29_1.png


You can also add several columns using ``fc.add_columns([Columns(...), Columns(...), etc])``.
