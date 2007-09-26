#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from twisted.internet import protocol, defer
from twisted.python import failure

import constants
import encoding
import msgformat
import contact

class InvalidMethod(Exception):
    """ The requested RPC method does not exist, or is not callable """

class KademliaProtocol(protocol.DatagramProtocol):
    """ Implements all low-level network-related functions of a Kademlia node """
    def sendRequest(self, contact, nodeID, request, kwargs):
        """ Sends a PING request to the specified contact
        
        @todo: This function will change to use a proper RPC PING
               as soon as we've done the RPC stuff.
        
        @param contact: The recipient of the RPC
        @type contact: kademlia.contact.Contact
        """
        msg = msgformat.RequestMessage(nodeID, request, kwargs)
        self._sendMessage(msg, contact)
        
    def sendResponse(self, contact, rpcID, nodeID, response):
        msg = msgformat.ResponseMessage(rpcID, nodeID, response)
        msgPrimitive = self.factory.translator.toPrimitive(msg)
        encodedMsg = self.factory.encoder.encode(msgPrimitive)
        self.transport.write(encodedMsg, (contact.address, contact.port))

    def sendError(self, contact, rpcID, nodeID, error):
        msg = msgformat.ErrorMessage(rpcID, nodeID, error)
        msgPrimitive = self.factory.translator.toPrimitive(msg)
        encodedMsg = self.factory.encoder.encode(msgPrimitive)
        self.transport.write(encodedMsg, (contact.address, contact.port))

    def _sendMessage(self, message, contact):
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
        df = defer.Deferred()
        #df.destContact = contact
        self.factory.sentMessages[message.id] = df
        encodedMsg = self.factory.encoder.encode(message)
        # Set the RPC timeout timer
        #reactor.callLater(constants.rpcTimeout, self.factory.msgTimout, message.id)
        df.setTimeout(constants.rpcTimeout, message.id, timeoutFunc=self.factory.msgTimeout)
        # Transmit the data
        self.transport.write(encodedMsg, (contact.address, contact.port))
        return df
    
    def datagramReceived(self, datagram, address):
        msgPrimitive = self.factory.encoder.decode(datagram)
        message = self.factory.translator.fromPrimitive(msgPrimitive)
        
        remoteContact = contact.Contact(message.nodeID, address[0], address[1])

        if isinstance(message, msgformat.RequestMessage):
            # This is an RPC method request; let the factory handle this
            self.factory.handleRPC(remoteContact, message.id, message.request, message.args)
        elif isinstance(message, msgformat.ResponseMessage):
            # Find the message that triggered this response
            if self.factory.sentMessagestids.has_key(message.id):
                df = self.factory.sentMessages[message.id]
                del self.factory.sentMessages[message.id]
                df.callback(message)
            else:
                # If the original message isn't found, it must have timed out
                #TODO: we should probably do something with this...
                pass


class NodePresence(protocol.ServerFactory):
    """ This provides network presence to the Node class
    
    @todo: investigate possible merging of this class with the (main) Node class
    """
    protocol = KademliaProtocol()

    def __init__(self, node, msgEncoder=encoding.Bencode(), msgTranslator=msgformat.DefaultFormat()):
        self.node = node
        self.encoder = msgEncoder
        self.translator = msgTranslator
        self.sentMessages = {}

    def handleRPC(self, senderContact, rpcID, method, args):
        """ Executes a local function in response to an RPC request """
        # Refresh the remote node's details in the local node's k-buckets    
        self.node.addContact(senderContact)
        
        # Set up the deferred callchain
        def handleError(error):
            self.protocol.sendError(senderContact, rpcID, error)
            
        def handleResult(result):
            self.protocol.sendResponse(senderContact, rpcID, result)
        
        df = defer.Deferred()
        df.addCallback(handleResult)
        df.addErrback(handleError)
                            
        # Execute the RPC
        f = getattr(self.node, method, None)
        if callable(f) and hasattr(f, 'rpcmethod'):
            # Call the exposed Node method and return the result to the deferred callback chain
            df.callback(f(msgArgs, *args, **kwargs))            
        else:
            # No such exposed method
            df.errback(failure.Failure(InvalidMethod, 'Invalid method: %s' % method))
        
    def msgTimeout(self, messageID):
        """ Called when an RPC request message times out """
        # Find the message that timed out
        if self.factory.sentMessagestids.has_key(messageID):
            df = self.factory.sentMessages[messageID]
            del self.factory.sentMessages[messageID]
            # The message's destination node is now considered to be dead;
            # raise an (asynchronous) TimeoutError exception to update the host node
            df.errback(failure.Failure(defer.TimeoutError('RPC request timed out')))
        else:
            # This should never be reached
            print "ERROR: deferred timed out, but is not present in factory's sent messages!"
