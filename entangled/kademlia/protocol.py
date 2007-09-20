#!/usr/bin/env python
#
# License: To be determined
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from twisted.internet.protocol import Protocol

class KademliaProtocol(Protocol):
    """ Implements all network-related functions of a Kademlia node """
    def __init__(self):
        pass
    
    def ping(self, contact):
        """ Sends a PING request to the specified contact
        
        @param contact: The recipient of the RPC
        @type contact: kademlia.contact.Contact
        """
        pass
