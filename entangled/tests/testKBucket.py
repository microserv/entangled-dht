#!/usr/bin/env python
#
# License: To be determined

import unittest

import kademlia.kbucket

class KBucketTest(unittest.TestCase):
    """ Test case for the KBucket class """
    def setUp(self):
        self.kbucket = kademlia.kbucket.KBucket()

    def testAddContact(self):
        pass

    def testGetContacts(self):
        pass

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(KBucketTest))
    return suite

if __name__ == '__main__':
    # If this module is executed from the commandline, run all its tests
    unittest.TextTestRunner().run(suite())
