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
import twisted.internet.selectreactor

import constants
import encoding
import msgtypes
import msgformat
import contact

reactor = twisted.internet.selectreactor.SelectReactor()

class InvalidMethod(Exception):
    """ The requested RPC method does not exist, or is not callable """


class KademliaProtocol(protocol.DatagramProtocol):
    """ Implements all low-level network-related functions of a Kademlia node """
    def __init__(self, node, msgEncoder=encoding.Bencode(), msgTranslator=msgformat.DefaultFormat()):
        self._node = node
        self._encoder = msgEncoder
        self._translator = msgTranslator
        self._sentMessages = {}
        
    def sendRPC(self, contact, method, args):
        """ Sends an RPC to the specified contact """
        rpcID, df = self._sendRequest(contact, method, args)
        self._sentMessages[rpcID] = df
        return df
    
    def datagramReceived(self, datagram, address):
        msgPrimitive = self._encoder.decode(datagram)
        message = self._translator.fromPrimitive(msgPrimitive)
        
        remoteContact = contact.Contact(message.nodeID, address[0], address[1], self)

        if isinstance(message, msgtypes.RequestMessage):
            # This is an RPC method request
            self._handleRPC(remoteContact, message.id, message.request, message.args)
        elif isinstance(message, msgtypes.ResponseMessage):
            # Find the message that triggered this response
            if self._sentMessages.has_key(message.id):
                df = self._sentMessages[message.id]
                del self._sentMessages[message.id]
                if isinstance(message, msgtypes.ErrorMessage):
                    # The RPC request gave an error
                    df.errback(InvalidMethod(message.response))
                else:
                    # We got a result from the RPC
                    df.callback(message.response)
            else:
                # If the original message isn't found, it must have timed out
                #TODO: we should probably do something with this...
                pass
    
    def _sendRequest(self, contact, request, args):
        """ Send an RPC request to the specified contact
        
        @todo: This function will change to use a proper RPC PING
               as soon as we've done the RPC stuff.
        
        @param contact: The recipient of the RPC
        @type contact: kademlia.contact.Contact
        """
        msg = msgtypes.RequestMessage(self._node.id, request, args)
        msgPrimitive = self._translator.toPrimitive(msg)
        encodedMsg = self._encoder.encode(msgPrimitive)
        
        df = defer.Deferred()
        # Set the RPC timeout timer
        reactor.callLater(constants.rpcTimeout, self._msgTimeout, msg.id)
        self.transport.write(encodedMsg, (contact.address, contact.port))
        return msg.id, df

    def _sendResponse(self, contact, rpcID, response, msgClass=msgtypes.ResponseMessage):
        """ Send a RPC response to the specified contact
        """
        msg = msgClass(rpcID, self._node.id, response)
        msgPrimitive = self._translator.toPrimitive(msg)
        encodedMsg = self._encoder.encode(msgPrimitive)
        self.transport.write(encodedMsg, (contact.address, contact.port))

    def _sendError(self, contact, rpcID, error):
        """ Send an RPC error message to the specified contact
        """
        self._sendResponse(contact, rpcID, error, msgtypes.ErrorMessage)

    def _handleRPC(self, senderContact, rpcID, method, args):
        """ Executes a local function in response to an RPC request """
        # Refresh the remote node's details in the local node's k-buckets    
        self._node.addContact(senderContact)
        
        # Set up the deferred callchain
        def handleError(f):
            self._sendError(senderContact, rpcID, f.getErrorMessage())
            
        def handleResult(result):
            self._sendResponse(senderContact, rpcID, result)
        
        df = defer.Deferred()
        df.addCallback(handleResult)
        df.addErrback(handleError)
        
        # Execute the RPC
        f = getattr(self._node, method, None)
        if callable(f) and hasattr(f, 'rpcmethod'):
            # Call the exposed Node method and return the result to the deferred callback chain
            try:
                if len(args):
                    result = f(args)
                else:
                    result = f()
            except Exception, e:
                df.errback(failure.Failure(e))
            else:
                df.callback(result)
        else:
            # No such exposed method
            df.errback(failure.Failure(InvalidMethod, 'Invalid method: %s' % method))
    
    def _msgTimeout(self, messageID):
        """ Called when an RPC request message times out """
        # Find the message that timed out
        if self._sentMessages.has_key(messageID):
            df = self._sentMessages[messageID]
            del self._sentMessages[messageID]
            # The message's destination node is now considered to be dead;
            # raise an (asynchronous) TimeoutError exception to update the host node
            df.errback(failure.Failure(defer.TimeoutError('RPC request timed out')))
        else:
            # This should never be reached
            print "ERROR: deferred timed out, but is not present in sent messages list!"
