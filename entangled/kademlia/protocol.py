#!/usr/bin/env python
#
# License: To be determined
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

class KademliaProtocol(DatagramProtocol):
    """ Implements all network-related functions of a Kademlia node """
    def __init__(self):
        pass
    
    def ping(self, contact):
        """ Sends a PING request to the specified contact
        
        @todo: This function will change to use a proper RPC PING
               as soon as we've done the RPC stuff.
        
        @param contact: The recipient of the RPC
        @type contact: kademlia.contact.Contact
        """
        self._sendMessage(contact, 'PING')


    def _sendMessage(self, contact, message):
        """ Send an RPC message via UDP 
        
        @todo: This function will change significantly as soon as
               the higher-level RPC stuff is sorted out. For instance,
               it needs to track RPC identification numbers, response
               timeouts, etc.
        
        @param contact: The recipient Kademlia node
        @type contact: kademlia.contact.Contact
        
        @param message: The message to send
        @type message: str
        """
        self.transport.connect(contact.address, contact.port)
        self.transport.write(datagram)
