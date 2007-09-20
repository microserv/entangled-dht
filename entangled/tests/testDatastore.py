#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

import unittest

import kademlia.datastore

import hashlib

class DataStoreTest(unittest.TestCase):
    """ Basic tests case for the reference DataStore API and implementation """
    def setUp(self):
        self.ds = kademlia.datastore.DataStore()
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
                self.ds[key] = value
            except Exception:
                import traceback
                self.fail('Failed writing the following data: key: "%s", data: "%s"\n  The error was: %s:' % (key, value, traceback.format_exc(5)))
            
        # Verify writing (test query ability)
        for key, value in self.cases:
            try:
                self.failUnless(key in self.ds, 'Key "%s" not found in DataStore!' % key)
            except Exception:
                import traceback
                self.fail('Failed verifying that the following key exists: "%s"\n  The error was: %s:' % (key, traceback.format_exc(5)))
        
        # Read back the data
        for key, value in self.cases:
            self.failUnlessEqual(self.ds[key], value, 'DataStore returned invalid data! Expected "%s", got "%s"' % (value, self.ds[key]))
    
    def testNonExistentKeys(self):
        for key, value in self.cases:
            self.failIf(key in self.ds, 'DataStore reports it has non-existent key: "%s"') 

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DataStoreTest))
    return suite

if __name__ == '__main__':
    # If this module is executed from the commandline, run all its tests
    unittest.TextTestRunner().run(suite())