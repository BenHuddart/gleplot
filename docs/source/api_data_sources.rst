Data sources
============

A series normally owns its numbers. It can instead carry a ``data_source``
that names columns in a table held elsewhere; the numbers are then looked up
when the figure is saved, through the ``data_provider`` passed to
:meth:`gleplot.Figure.savefig`.

Sources
-------

.. autoclass:: gleplot.DataSource

.. autoclass:: gleplot.InlineData

.. autoclass:: gleplot.ColumnRef

.. autoclass:: gleplot.GridRef

Providers
---------

.. autoclass:: gleplot.DataProvider
   :members:

.. autoclass:: gleplot.TableData
   :members:

.. autoclass:: gleplot.DictDataProvider
   :members:

Unresolved references
---------------------

.. autoclass:: gleplot.DanglingSourceRef
   :members:

.. autoclass:: gleplot.DanglingSourceWarning
