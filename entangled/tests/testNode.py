#!/usr/bin/env python
#
# License: To be determined

import unittest

import kademlia.node

class NodeIDTest(unittest.TestCase):
    """ Test case for the Node class's ID """
    def setUp(self):
        self.node = kademlia.node.Node()

    def testUniqueness(self):
        """ Tests the uniqueness of the values created by the NodeID generator 
        """
        generatedIDs = []
        for i in range(100):
            newID = self.node._generateID()
            # ugly uniqueness test
            self.failIf(newID in generatedIDs, 'Generated ID #%d not unique!' % (i+1))
            generatedIDs.append(newID)
    
    def testKeyLength(self):
        """ Tests the key Node ID key length """
        for i in range(20):
            id = self.node._generateID()
            # Key length: 20 bytes == 160 bits
            self.failUnlessEqual(len(id), 20, 'Length of generated ID is incorrect! Expected 160 bits, got %d bits.' % (len(id)*8))

    def testDistance(self):
        """ Test to see if distance method returns correct result"""
        
        # testList holds a couple 3-tuple (variable1, variable2, result)
        basicTestList = [('123456789','123456789', 0L), ('12345', '98765', 34527773184L)]

        for test in basicTestList:
            result = self.node._distance(test[0], test[1])
            self.failIf(result != test[2], 'Result of _distance() should be %s but %s returned' % (test[2], result))

        baseIp = '146.64.19.111'
        ipTestList = ['146.64.29.222', '192.68.19.333']

        distanceOne = self.node._distance(baseIp, ipTestList[0])
        distanceTwo = self.node._distance(baseIp, ipTestList[1])

        self.failIf(distanceOne > distanceTwo, '%s should be closer to the base ip %s than %s' % (ipTestList[0], baseIp, ipTestList[1]))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(NodeIDTest))
    return suite

if __name__ == '__main__':
    # If this module is executed from the commandline, run all its tests
    unittest.TextTestRunner().run(suite())
