#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

import time
import unittest

from twisted.internet import defer
from twisted.python import failure
import twisted.internet.selectreactor

import kademlia.protocol
import kademlia.contact
import kademlia.constants
from kademlia.node import rpcmethod

class FakeNode(object):
    """ A fake node object implementing some RPC and non-RPC methods to 
    test the Kademlia protocol's behaviour
    """
    def __init__(self, id):
        self.id = id
        self.contacts = []
        
    @rpcmethod
    def ping(self):
        return 'pong'
    
    def pingNoRPC(self):
        return 'pong'
    
    @rpcmethod
    def echo(self, value):
        return value
    
    def addContact(self, contact):
        self.contacts.append(contact)
    
    def removeContact(self, contact):
        self.contacts.remove(contact)

    def indirectPingContact(self, protocol, contact):
        """ Pings the given contact (using the specified KademliaProtocol
        object, not the direct Contact API), and removes the contact
        on a timeout """
        df = protocol.sendRPC(contact, 'ping', {})
        def handleError(f):
            if f.check(defer.TimeoutError):
                self.removeContact(contact)
                #f.trap(defer.TimeoutError)
                return f
            else:
                # This is some other error
                return f
        df.addErrback(handleError)
        return df
        

class KademliaProtocolTest(unittest.TestCase):
    """ Test case for the NodePresence class """
    def setUp(self):
        del kademlia.protocol.reactor
        kademlia.protocol.reactor = twisted.internet.selectreactor.SelectReactor()
        self.node = FakeNode('node1')
        self.protocol = kademlia.protocol.KademliaProtocol(self.node)

    def testReactor(self):
        """ Tests if the reactor can start/stop the protocol correctly """
        kademlia.protocol.reactor.listenUDP(0, self.protocol)
        kademlia.protocol.reactor.callLater(0, kademlia.protocol.reactor.stop)
        kademlia.protocol.reactor.run()

    def testRPCPing(self):
        """ Tests if an RPC message sent to a dead remote node time out correctly """
        def tempMsgTimeout(messageID):
            """ Replacement testing method for the KademliaProtol's normal
            _msgTimeout() method """
            if self.protocol._sentMessages.has_key(messageID):
                df = self.protocol._sentMessages[messageID]
                del self.protocol._sentMessages[messageID]
                df.errback(failure.Failure(defer.TimeoutError('RPC request timed out')))
            else:
                print "ERROR: deferred timed out, but is not present in sent messages list!"
            kademlia.protocol.reactor.stop()
        
        deadContact = kademlia.contact.Contact('node2', '127.0.0.1', 91824, self.protocol)
        self.node.addContact(deadContact)
        # Make sure the contact was added
        self.failIf(deadContact not in self.node.contacts, 'Contact not added to fake node (error in test code)')
        self.protocol._msgTimeout = tempMsgTimeout
        # Set the timeout to 0 for testing
        tempTimeout = kademlia.constants.rpcTimeout
        kademlia.constants.rpcTimeout = 0
        kademlia.protocol.reactor.listenUDP(0, self.protocol)            
        # Run the PING RPC (which should timeout)
        df = self.node.indirectPingContact(self.protocol, deadContact)
        # Stop the reactor if a result arrives (timeout or not)
        df.addBoth(lambda _: kademlia.protocol.reactor.stop)
        kademlia.protocol.reactor.run()
        # See if the contact was removed due to the timeout
        self.failIf(deadContact in self.node.contacts, 'RPC timed out, but contact was not removed!')
        # Restore the global timeout
        kademlia.constants.rpcTimeout = tempTimeout
        
    def testRPCRequest(self):
        """ Tests if an inbound RPC request is executed and responded to correctly """
        remoteContact = kademlia.contact.Contact('node2', '127.0.0.1', 91824, self.protocol)
        self.node.addContact(remoteContact)
        self.error = None
        
        def handleError(f):
            self.error = 'An RPC error occurred: %s' % f.getErrorMessage()
            
        
        def handleResult(result):
            if result != 'pong':
                self.error = 'Result from RPC is incorrect; expected "pong", got "%s"' % result
            
        # Publish the "local" node on the network    
        kademlia.protocol.reactor.listenUDP(91824, self.protocol)
        # Simulate the RPC
        df = remoteContact.ping()
        df.addCallback(handleResult)
        df.addErrback(handleError)
        df.addBoth(lambda _: kademlia.protocol.reactor.stop())
        kademlia.protocol.reactor.run()
        self.failIf(self.error, self.error)
        # The list of sent RPC messages should be empty at this stage
        self.failUnlessEqual(len(self.protocol._sentMessages), 0, 'The protocol is still waiting for an RPC result, but the transaction is already done!')
        

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(KademliaProtocolTest))
    return suite

if __name__ == '__main__':
    # If this module is executed from the commandline, run all its tests
    unittest.TextTestRunner().run(suite())