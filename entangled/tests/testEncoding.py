#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

import unittest

import kademlia.encoding

class BencodeTest(unittest.TestCase):
    """ Basic tests case for the Bencode implementation """
    def setUp(self):
        self.encoding = kademlia.encoding.Bencode()
        # Thanks goes to wikipedia for the initial test cases ;-)
        self.cases = ((42, 'i42e'),
                      ('spam', '4:spam'),
                      (['spam',42], 'l4:spami42ee'),
                      ({'foo':42, 'bar':'spam'}, 'd3:bar4:spam3:fooi42ee'))
                      
    def testEncoder(self):
        """ Tests the bencode encoder """
        for value, encodedValue in self.cases:
            result = self.encoding.encode(value)
            self.failUnlessEqual(result, encodedValue, 'Value "%s" not correctly encoded! Expected "%s", got "%s"' % (value, encodedValue, result))
        
    def testDecoder(self):
        """ Tests the bencode decoder """
        for value, encodedValue in self.cases:
            result = self.encoding.decode(encodedValue)
            self.failUnlessEqual(result, value, 'Value "%s" not correctly decoded! Expected "%s", got "%s"' % (encodedValue, value, result))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BencodeTest))
    return suite

if __name__ == '__main__':
    # If this module is executed from the commandline, run all its tests
    unittest.TextTestRunner().run(suite())
