#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

import unittest
import time

import entangled.kademlia.datastore

import hashlib

class DictDataStoreTest(unittest.TestCase):
    """ Basic tests case for the reference DataStore API and implementation """
    def setUp(self):
        if not hasattr(self, 'ds'):
            self.ds = entangled.kademlia.datastore.DictDataStore()
        h = hashlib.sha1()
        h.update('g')
        hashKey = h.digest()
        self.cases = (('a', 'hello there\nthis is a test'),
                      ('b', unicode('jasdklfjklsdj;f2352352ljklzsdlkjkasf\ndsjklafsd')),
                      ('e', 123),
                      ('f', [('this', 'is', 1), {'complex': 'data entry'}]),
                      ('aMuchLongerKeyThanAnyOfThePreviousOnes', 'some data'),
                      (hashKey, 'some data'))
    
    def testReadWrite(self):
        # Test write ability
        for key, value in self.cases:
            try:
                now = time.time()
                self.ds.setItem(key, value, now, now, 'node1')
            except Exception:
                import traceback
                self.fail('Failed writing the following data: key: "%s", data: "%s"\n  The error was: %s:' % (key, value, traceback.format_exc(5)))
        
        # Verify writing (test query ability)
        for key, value in self.cases:
            try:
                self.failUnless(key in self.ds.keys(), 'Key "%s" not found in DataStore!' % key)
            except Exception:
                import traceback
                self.fail('Failed verifying that the following key exists: "%s"\n  The error was: %s:' % (key, traceback.format_exc(5)))
        
        # Read back the data
        for key, value in self.cases:
            self.failUnlessEqual(self.ds[key], value, 'DataStore returned invalid data! Expected "%s", got "%s"' % (value, self.ds[key]))
    
    def testNonExistentKeys(self):
        for key, value in self.cases:
            self.failIf(key in self.ds, 'DataStore reports it has non-existent key: "%s"' % key)
            
    def testReplace(self):
        # First write with fake values
        for key, value in self.cases:
            try:
                now = time.time()
                self.ds.setItem(key, 'abc', now, now, 'node1')
            except Exception:
                import traceback
                self.fail('Failed writing the following data: key: "%s", data: "%s"\n  The error was: %s:' % (key, value, traceback.format_exc(5)))
        
        # write this stuff a second time, with the real values
        for key, value in self.cases:
            try:
                now = time.time()
                self.ds.setItem(key, value, now, 'node1', now)
            except Exception:
                import traceback
                self.fail('Failed writing the following data: key: "%s", data: "%s"\n  The error was: %s:' % (key, value, traceback.format_exc(5)))

        self.failUnlessEqual(len(self.ds.keys()), len(self.cases), 'Values did not get overwritten properly; expected %d keys, got %d' % (len(self.cases), len(self.ds.keys())))
        # Read back the data
        for key, value in self.cases:
            self.failUnlessEqual(self.ds[key], value, 'DataStore returned invalid data! Expected "%s", got "%s"' % (value, self.ds[key]))

    def testDelete(self):
        # First write with fake values
        for key, value in self.cases:
            try:
                now = time.time()
                self.ds.setItem(key, 'abc', now, now, 'node1')
            except Exception:
                import traceback
                self.fail('Failed writing the following data: key: "%s", data: "%s"\n  The error was: %s:' % (key, value, traceback.format_exc(5)))
        
        self.failUnlessEqual(len(self.ds.keys()), len(self.cases), 'Values did not get stored properly; expected %d keys, got %d' % (len(self.cases), len(self.ds.keys())))
        
        # Delete an item from the data
        key, value == self.cases[0]
        del self.ds[key]
        self.failUnlessEqual(len(self.ds.keys()), len(self.cases)-1, 'Value was not deleted; expected %d keys, got %d' % (len(self.cases)-1, len(self.ds.keys())))
        self.failIf(key in self.ds.keys(), 'Key was not deleted: %s' % key)


class SQLiteDataStoreTest(DictDataStoreTest):
    def setUp(self):
        self.ds = entangled.kademlia.datastore.SQLiteDataStore()
        DictDataStoreTest.setUp(self)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DictDataStoreTest))
    suite.addTest(unittest.makeSuite(SQLiteDataStoreTest))
    return suite


if __name__ == '__main__':
    # If this module is executed from the commandline, run all its tests
    unittest.TextTestRunner().run(suite())