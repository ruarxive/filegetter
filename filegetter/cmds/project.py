# -* coding: utf-8 -*-
import configparser
import json
import logging
import os
import csv
import time
from timeit import default_timer as timer
from zipfile import ZipFile, ZIP_DEFLATED
import gzip
from urllib.parse import urlparse
import requests
import xmltodict

from ..common import get_dict_value, set_dict_value, update_dict_values
from ..constants import DEFAULT_DELAY, FIELD_SPLITTER
from ..storage import FilesystemStorage, ZipFileStorage
try:
    import aria2p
except ImportError:
    pass

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
FILE_SIZE_DOWNLOAD_LIMIT = 270000000
DEFAULT_TIMEOUT = 10
PARAM_SPLITTER = ';'

def load_file_list(filename, encoding='utf8'):
    """Reads file and returns list of strings as list"""
    flist = []
    with open(filename, 'r', encoding=encoding) as f:
        for l in f:
            flist.append(l.rstrip())
    return flist

def load_csv_data(filename, key, encoding='utf8', delimiter=';'):
    """Reads CSV file and returns list records as array of dicts"""
    flist = {}
    with open(filename, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for r in reader:
            flist[r[key]] = r
    return flist

def load_processed_files_list(filename, encoding='utf8', delimiter=','):
    """Reads file with list of processed files"""
    return load_csv_data(filename, 'url', encoding='utf8', delimiter=',')


def _url_replacer(url, params, query_mode=False):
    """Replaces urp params"""
    if query_mode:
        query_char = '?'
        splitter = '&'
    else:
        splitter = PARAM_SPLITTER
        query_char = PARAM_SPLITTER
    parsed = urlparse(url)
    finalparams = []
    for k, v in params.items():
        finalparams.append('%s=%s' % (str(k), str(v)))
    return parsed.geturl() + query_char + splitter.join(finalparams)



class FilegetterBuilder:
    """Filegetter project builder"""

    def __init__(self, project_path=None):
        self.http = requests.Session()
        self.project_path = os.getcwd() if project_path is None else project_path
        self.config_filename = os.path.join(self.project_path, 'filegetter.cfg')
        self.__read_config(self.config_filename)
        pass

    def __read_config(self, filename):
        self.config = None
        if os.path.exists(self.config_filename):
            conf = configparser.ConfigParser()
            conf.read(filename, encoding='utf8')
            self.config = conf

            self.id = conf.get('project', 'id') if conf.has_option('settings', 'id') else None
            self.name = conf.get('project', 'name')
            self.data_key = conf.get('data', 'data_key') if conf.has_option('data', 'data_key') else None
            self.source = conf.get('project', 'source')
            self.source_type = conf.get('project', 'source_type')
            self.field_splitter = conf.get('project', 'splitter') if conf.has_option('settings',
                                                                                      'splitter') else FIELD_SPLITTER
            self.delimiter = conf.get('project', 'delimiter') if conf.has_option('project', 'delimiter') else ','
            self.delimiter = '\t' if self.delimiter == 'tab' else ','

            storagedir = conf.get('storage', 'storage_path') if conf.has_option('storage',
                                                                                   'storage_path') else 'storage'
            self.storagedir = os.path.join(self.project_path, storagedir)
            self.storage_type = conf.get('storage', 'storage_type')

            if conf.has_section('files'):
                self.fetch_mode = conf.get('files', 'fetch_mode')
                self.transfer_ext = conf.get('files', 'transfer_ext') if conf.has_option('files', 'transfer_ext') else None
                self.default_ext = conf.get('files', 'default_ext') if conf.has_option('files', 'default_ext') else None
                self.files_keys = conf.get('files', 'keys').split(',')
                self.root_url = conf.get('files', 'root_url')
                self.storage_mode = conf.get('files', 'storage_mode') if conf.has_option('files', 'storage_mode') else 'filepath'
                self.file_storage_type = conf.get('files', 'file_storage_type') if conf.has_option('files', 'file_storage_type') else 'zip'
                self.use_aria2 = conf.get('files', 'use_aria2') if conf.has_option('files', 'use_aria2') else 'False'



    def init(self, url, pagekey, pagesize, datakey, itemkey, changekey, iterateby, http_mode, work_modes):
        """[TBD] Unfinished method. Don't use it please"""
        conf = self.__read_config(self.config_filename)
        if conf is None:
            print('Config file not found. Please run in project directory')
            return
        pass

    def run(self, be_careful=False):
        """Downloads all files associated with this API data"""
        headers = {'User-Agent' : DEFAULT_USER_AGENT}
        if self.config is None:
            print('Config file not found. Please run in project directory')
            return
        if not os.path.exists(self.storagedir):
            os.mkdir(self.storagedir)
        if self.storage_type != 'zip':
            print('Only zip storage supported right now')
            return
        uniq_ids = []

        allfiles_name = os.path.join(self.storagedir, 'allfiles.csv')
        if not os.path.exists(allfiles_name):
            if self.source_type == 'list':
                f = open(self.source, 'r', encoding='utf8')
                for l in f:
                    uniq_ids.append(l)
                f.close()
            elif self.source_type == 'csv':
                f = open(self.source, 'r', encoding='utf8')
                reader = csv.DictReader(f, delimiter=self.delimiter)
                for row in reader:
                    if len(row[self.data_key]) > 0:
                        uniq_ids.append(row[self.data_key])
                f.close()
            elif self.source_type == 'jsonl':
                f = open(self.source, 'r', encoding='utf8')
                for l in f:
                    row = json.loads(l)
                    if self.data_key:
                        iterate_data = get_dict_value(row, self.data_key, splitter=self.field_splitter)
                    else:
                        iterate_data = row
                    for item in iterate_data:
                        if item:
                            for key in self.files_keys:
                                file_data = get_dict_value(item, key, as_array=True, splitter=self.field_splitter)
                                if file_data:
                                    for uniq_id in file_data:
                                        if uniq_id is not None:
                                            uniq_ids.append(uniq_id)
                    uniq_ids.append(row[self.data_key])
                f.close()

            logging.info('Storing all filenames')
            f = open(allfiles_name, 'w', encoding='utf8')
            for u in uniq_ids:
                f.write(str(u) + '\n')
            f.close()
        else:
            logging.info('Load all filenames')
            uniq_ids = load_file_list(allfiles_name)
        # Start download
        processed_files = {}
        skipped_files_dict = {}
        files_storage_file = os.path.join(self.storagedir, 'files.zip')
        files_list_storage = os.path.join(self.storagedir, 'processed.csv')
        w_headers = False
        if os.path.exists(files_list_storage):
            processed_files = load_processed_files_list(files_list_storage, encoding='utf8')
            list_file = open(files_list_storage, 'a', encoding='utf8')
        else:
            list_file = open(files_list_storage, 'w', encoding='utf8')
            fields = ['url', 'filename', 'mime', 'ext', 'disp_name',  'filesize']
            w_headers = True
        writer = csv.writer(list_file, delimiter=',')
        if w_headers:
            writer.writerow(fields)

        use_aria2 = True if self.use_aria2 == 'True' else False
        if use_aria2:
            aria2 = aria2p.API(
                aria2p.Client(
                    host="http://localhost",
                    port=6800,
                    secret=""
                )
            )
        else:
            aria2 = None
        if self.file_storage_type == 'zip':
            fstorage = ZipFileStorage(files_storage_file, mode='a', compression=ZIP_DEFLATED)
        elif self.file_storage_type == 'filesystem':
            fstorage = FilesystemStorage(os.path.join('storage', 'files'))


        n = 0
        for uniq_id in uniq_ids:
            if self.fetch_mode == 'prefix':
                url = self.root_url + str(uniq_id)
            elif self.fetch_mode == 'pattern':
                url = self.root_url.format(uniq_id)
            n += 1
            if n % 50 == 0:
                logging.info('Downloaded %d files' % (n))
            if self.storage_mode == 'filepath':
                filename = urlparse(url).path
            else:
                filename = str(uniq_id)

            logging.info('Processing %s as %s' % (url, filename))
#            if fstorage.exists(filename):
            if url in processed_files.keys():
                logging.info('File %s already stored' % (filename))
            else:
                if not use_aria2:
                    response = self.http.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, verify=False)
                    if 'content-type' in response.headers.keys():
                        mime = response.headers['content-type']
                    else:
                        mime = None
                    if 'content-disposition' in response.headers.keys():
                        disp_name = response.headers['content-disposition'].rsplit('filename=', 1)[-1].strip('"')
                        disp_ext = disp_name.rsplit('.', 1)[-1].lower()
                    else:
                        disp_name = None
                        disp_ext = None
                    ext = disp_ext
                    if self.transfer_ext is not None:
                        if ext is not None:
                            filename = filename + "." + ext
                    elif self.default_ext is not None:
                        filename = filename + "." + self.default_ext
                    record = [url, filename, mime, ext, disp_name, str(len(response.content))]
                    fstorage.store(filename, response.content)
                    writer.writerow(map(str, record))
                    processed_files[url] = record
                else:
                    aria2.add_uris(uris=[url, ],
                                   options={'out': filename, 'dir': os.path.abspath(os.path.join('storage', 'files'))})

        fstorage.close()
        list_file.close()
