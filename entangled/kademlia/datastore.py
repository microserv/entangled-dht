#!/usr/bin/env python
#
# License: To be determined
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import UserDict
import sqlite3

class DataStore(UserDict.DictMixin):
    """ Future interface for classes implementing physical storage for the Kademlia DHT;
    currently this is an *example* of a in-memory SQL database-based datastore
    
    @note: This provides an interface for a dict-like object
    
    @todo: discuss whether or not it's necessary to define DataStore as an interface; it may
           be sufficient to require a dict-like object as the data storage object
    """
    def __init__(self):
        self._db = sqlite3.connect(':memory:')
        self._db.execute('create table data(key, value)')
        self._cursor = self._db.cursor()
    
    def __getitem__(self, key):
        try:
            value = self._cursor.execute('select value from data where key=?', key).fetchone()[0]
        except TypeError:
            raise KeyError, key
        else:
            return value
        
    def __setitem__(self, key, value):
        self._cursor.execute('insert into data(key, value) values (?, ?)', (key, value))
