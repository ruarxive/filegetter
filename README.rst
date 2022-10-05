==============================================================
filegetter -- a command-line tool to collect files from public data sources
==============================================================


filegetter is a file collection command-line tool that help to download a lot of files with URLS in YAML configuration files

.. contents::

.. section-numbering::


History
=======
This tool was developed to automate files collection from datasets created by other tools.
Several examples in `examples` directory shows it's usage in practice.

Main features
=============


* Any list of URLs supported: CSV, JSON lines or plain text
* URL prefixes supported
* Saves result to filesystem or ZIP container
* Stores report as CSV file 



Installation
============


.. code-block:: bash

    # Make sure we have an up-to-date version of pip and setuptools:
    $ pip install --upgrade pip setuptools

    $ pip install --upgrade filegetter


(If ``pip`` installation fails for some reason, you can try
``easy_install filegetter`` as a fallback.)


Python version
--------------

Python version 3.6 or greater is required.


Quickstart
==========

This example is about archival of files of Russian federal draft budget law 2023-2025.

.. code-block:: bash

    $ mkdir budget2023
    $ cd budget2023

Create file filegetter.cfg as:

.. code-block:: bash

    [project]
    name = budget2023
    description = Budget of RF 2023 documents
    source = dataset.csv
    source_type = csv
    delimiter = ,

    [data]
    data_key = href

    [files]
    fetch_mode = prefix
    root_url = https://sozd.duma.gov.ru
    keys = href
    storage_mode = filepath
    transfer_ext = True

    [storage]
    storage_type = zip
    compression = True


Execute command "run" to collect the data. Result stored in "storage.zip"

.. code-block:: bash

    $ filegetter run

Usage
=====

Synopsis:

.. code-block:: bash

    $ filegetter [flags] [command] inputfile


See also ``filegetter --help``.



Config options
==============

project
-------
* name - short name of the project
* description - text that explains what for is this project
* source - source data file, full or relational path
* source_type - type of the data source, csv, jsonl or list
* delimiter - splitter character, by default comma ','


data
----
* data_key - key with URLs or URL part

files
-----
* fetch_mode - file fetch mode. Could be 'prefix' or 'id'. Prefix
* root_url - root url / prefix  for files
* keys - list of keys with urls/file id's to search for files to save
* storage_mode - a way how files stored in storage/files.zip. By default 'filepath' and files storaged same way as they presented in url
* default_ext - set default extension, for example jpg or csv
* transfer_ext - adds extension to files if file have no extension

storage
-------
* storage_type - type of local storage. 'zip' is local zip file is default one
* compression - if True than compressed ZIP file used, less space used, more CPU time processing data

