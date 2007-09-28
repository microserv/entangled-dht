#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import hashlib, random, math

from twisted.internet import defer

import constants
import kbucket
import datastore
import protocol
from contact import Contact

def rpcmethod(func):
    """ Decorator to expose methods as RPC calls """
    func.rpcmethod = True
    return func

class Node(object):
    def __init__(self, knownNodeAddresses=None, dataStore=None, networkProtocol=None):
        """
        @param knownNodeAddresses: A sequence of tuples containing IP address
                                   information for existing nodes on the
                                   Kademlia network, in the format:
                                   C{(<ip address>, (udp port>)}
        @type knownNodeAddresses: tuple
        """
        self.id = self._generateID()
        # Create k-buckets (for storing contacts)
        self._buckets = []
        for i in range(160):
            self._buckets.append(kbucket.KBucket())
        # Initialize this node's network access mechanisms
        if networkProtocol == None:
            self._protocol = protocol.KademliaProtocol(self)
        else:
            self._protocol = networkProtocol
        # Initialize the data storage mechanism used by this node
        if dataStore == None:
            self._dataStore = datastore.DataStore()
        else:
            self._dataStore = dataStore
            
    def joinNetwork(self, udpPort=81172):
        """ Causes the Node to join the Kademlia network; this will execute
        the Twisted reactor's main loop """
        protocol.reactor.listenUDP(udpPort, self._protocol)
        # Initiate the Kademlia joining sequence
        df = self._iterativeFindNode(self.id)
        #TODO: Refresh buckets
        protocol.reactor.run()

    def _iterativeFindNode(self, key):
        """ The basic Kademlia iterative node lookup operation
        
        This builds a list of k "closest" contacts through iterative use of
        the "FIND_NODE" RPC """
        print '\n_iterativeFindNode() called'
        shortlist = self._findCloseNodes(key, constants.alpha)
        # Note the closest known node
        #TODO: possible IndexError exception here:
        closestNode = [shortlist[0], None] # format: [<current closest node>, <previous closest node>]
        for contact in shortlist:
            if self._distance(key, contact.id) < self._distance(key, closestNode[0].id):
                closestNode[0] = contact
    
        def extendShortlist(responseMsg):
            #print 'deferred callback to extendShortlist:'
            #print '==========='
            # Mark this node as active
            if responseMsg.nodeID not in activeContacts:
                activeContacts.append(responseMsg.nodeID)
            # Now grow extend the shortlist with the returned contacts
            result = responseMsg.response
            #TODO: some validation on the result (for guarding against attacks)
            for contactTriple in result:
                testContact = Contact(contactTriple[0], contactTriple[1], contactTriple[2], self._protocol)
                if testContact not in shortlist:
                    #TODO: currently, the shortlist can grow to more than k entries... should probably fix this, but it isn't fatal
                    shortlist.append(testContact)
                    if self._distance(key, testContact.id) < self._distance(key, closestNode[0].id):
                        closestNode[0] = testContact
            return responseMsg.nodeID
        
        def removeFromShortlist(failure):
            #print 'deferred errback to extendShortlist:', failure
            #print '==========='
            failure.trap(protocol.TimeoutError)
            deadContactID = failure.getErrorMessage()
            if deadContactID in shortlist:
                shortlist.remove(deadContactID)
            return deadContactID  
                
        def cancelActiveProbe(contactID):
            #if contactID in activeProbes:
                #activeProbes.remove(contactID)
            activeProbes.pop()
            if len(activeProbes) == 0 and len(pendingIterationCalls):
                # Force the iteration
                pendingIterationCalls[0].cancel()
                searchIteration()

        # Send parallel, asynchronous FIND_NODE RPCs to the shortlist of contacts
        alreadyContacted = []
        activeProbes = []
        # A list of known-to-be-active remote nodes
        activeContacts = []
        pendingIterationCalls = []
        #print 'closestNode:', closestNode[0]
        #print 'previousClosestNode:', closestNode[1]
        def searchIteration():
            # See if should continue the search
            if len(activeContacts) >= constants.k or closestNode[0] == closestNode[1]:
                # Ok, we're done; either we have accumulated k active contacts or
                # no improvement in closestNode has been noted
                print 'len(activeContacts):', len(activeContacts)
                print 'closestNode:', closestNode[0]
                print 'previousClosestNode:', closestNode[1]
                #print '!!!!!!!ADDING CONTACTS!!!!!!!!!!'
                #for contact in activeContacts:
                #    self.addContact(contact)
                print 'stopping iterations....'
                outerDf.callback(closestNode[0])
            else:
                # The search continues...
                contactedNow = 0
                for contact in shortlist:
                    if contact.id not in alreadyContacted:
                        print 'adding probe to list...'
                        activeProbes.append(contact.id)
                        df = contact.findNode(key, rawResponse=True)
                        df.addCallback(extendShortlist)
                        df.addErrback(removeFromShortlist)
                        df.addCallback(cancelActiveProbe)
                        alreadyContacted.append(contact.id)
                        contactedNow += 1
                    if contactedNow == constants.alpha:
                        break
                closestNode[1] = closestNode[0]
                # Schedule the next iteration (Kademlia uses loose parallelism)
                call = protocol.reactor.callLater(constants.iterativeLookupDelay, searchIteration)
                pendingIterationCalls.append(call)
                
        outerDf = defer.Deferred()
        # Start the iterations
        searchIteration()
        return outerDf


    @rpcmethod
    def findNode(self, key, **kwargs):
        """ Finds a number of known nodes closest to the node/value with the
        specified key.
        
        @param key: the 160-bit key (i.e. the node or value ID) to search for
        @type key: str
        
        @return: A list of contact triples closest to the specified key. 
                 This method will return C{k} (or C{count}, if specified)
                 contacts if at all possible; it will only return fewer if the
                 node is returning all of the contacts that it knows of.
        @rtype: list
        """
        # Get the sender's ID (if any)
        if '_rpcNodeID' in kwargs:
            rpcSenderID = kwargs['_rpcNodeID']
        else:
            rpcSenderID = None
            
        print 'findNode called, rpc ID:', rpcSenderID
        contacts = self._findCloseNodes(key, constants.k, rpcSenderID)
        contactTriples = []
        for contact in contacts:
            contactTriples.append( (contact.id, contact.address, contact.port) )
        return contactTriples

    def _findCloseNodes(self, key, count, _rpcNodeID=None):
        """ Finds a number of known nodes closest to the node/value with the
        specified key.
        
        @param key: the 160-bit key (i.e. the node or value ID) to search for
        @type key: str
        @param count: the amount of contacts to return
        @type count: int
        @param _rpcNodeID: Used during RPC, this is be the sender's Node ID
                           Whatever ID is passed in the paramater will get
                           excluded from the list of returned contacts.
        @type _rpcNodeID: str
        
        @return: A list of node contacts (C{kademlia.contact.Contact instances})
                 closest to the specified key. 
                 This method will return C{k} (or C{count}, if specified)
                 contacts if at all possible; it will only return fewer if the
                 node is returning all of the contacts that it knows of.
        @rtype: list
        """
        if key == self.id:
            bucketIndex = 0 #TODO: maybe not allow this to continue?
        else:
            bucketIndex = self._kbucketIndex(key)
        closestNodes = self._buckets[bucketIndex].getContacts(constants.k, _rpcNodeID)
        # The node must return k contacts, unless it does not know at least 8
        i = 1
        canGoLower = bucketIndex-i >= 0
        canGoHigher = bucketIndex+i < 160
        # Fill up the node list to k nodes, starting with the closest neighbouring nodes known 
        while len(closestNodes) < constants.k and (canGoLower or canGoHigher):
            #TODO: this may need to be optimized
            if canGoLower:
                closestNodes.extend(self._buckets[bucketIndex-i].getContacts(constants.k - len(closestNodes), _rpcNodeID))
                canGoLower = bucketIndex-(i+1) >= 0
            if canGoHigher:
                closestNodes.extend(self._buckets[bucketIndex+i].getContacts(constants.k - len(closestNodes), _rpcNodeID))
                canGoHigher = bucketIndex+(i+1) < 160
            i += 1
        return closestNodes

    def addContact(self, contact):
        """ Add/update the given contact

        @param contact: kademlia.contact.Contact 
        @note: It is assumed that the bucket is -
            1) the contact is alive - timeout stuff sorted before method called!
            2) not full
            3) contact is in list

            If the exception is raised then a new contact has arrived
            and then the bucket should be resorted i.e. closest contacts are in bucket
        """
        if contact.id == self.id:
            return
        bucketIndex = self._kbucketIndex(contact.id)
        try:
            self._buckets[bucketIndex].addContact(contact)
        except kbucket.BucketFull, e:
            print 'addContact(): Warning: ', e
            updateContacts(contact)

    def removeContact(self, contact):
        """ Remove the specified contact from this node's table of known nodes
        
        @param contact: The contact to remove
        @type contact: kademlia.contact.Contact
        
        @raise ValueError: Raised if the contact isn't found
        """
        bucketIndex = self._kbucketIndex(contact.id)
        try:
            self._buckets[bucketIndex].remove(contact)
        except ValueError:
            print 'removeContact(): Warning: ', e
            raise

    def updateContacts(self, contact):
        """ Update all current contacts in bucket by sending a ping request to all of them
            Then determine the closest set of contacts
        """
        contactList = self._buckets.getContacts("ALL")
        for currentContact in contactList:
            # PING(currentContact)
            pass
        
        # COMPARE RTT (round trip time)

    @rpcmethod
    def store(self, key, value):
        """ Store the received data in the local hash table
        
        @todo: Since the data (value) may be large, passing it around as a buffer
               (which is the case currently) might not be a good idea... will have
               to fix this (perhaps use a stream from the Protocol class?)
               Please comment on the relevant Trac ticket (or open a new one) if you
               have ideas
               -Francois
        """
        self._dataStore[key] = value
    
    @rpcmethod
    def findValue(self, key):
        """ Return the value associated with the specified key if present in
        this node's data, otherwise execute FIND_NODE for the key
        
        @todo: This function will need some fixup as soon as the Protocol class is
               implemented; for instance, the Protocol class needs to know that
               findNode() is being called if the value isn't found... we might want
               to start applying some custom Exceptions.
               For this reason, I am not implementing a unit test for this function;
               it is pretty pointless at this stage.
        
        @param key: The hashtable key of the data to return
        @type key: str
        """
        if key in self._dataStore:
            return self._dataStore[key]
        else:
            return self.findNode(key)

    @rpcmethod
    def ping(self):
        """ Used to verify contact between two Kademlia nodes """
        return 'pong'

    def _generateID(self):
        """ Generates a 160-bit pseudo-random identifier
        
        @return: A globally unique 160-bit pseudo-random identifier
        @rtype: str
        """
        hash = hashlib.sha1()
        hash.update(str(random.getrandbits(255)))  
        return hash.digest()

    def _distance(self, keyOne, keyTwo):
        """ Calculate the XOR result between two string variables
        
        @return: XOR result of two long variables
        @rtype: long
        """
        valKeyOne = long(keyOne.encode('hex'), 16)
        valKeyTwo = long(keyTwo.encode('hex'), 16)
        return valKeyOne ^ valKeyTwo
    
    def _kbucketIndex(self, key):
        """ Calculate the index of the k-bucket which is responsible for the
        specified key
        
        @param key: The key for which to find the appropriate k-bucket index
        @type key: str
        
        @return: The index of the k-bucket responsible for the specified key
        @rtype: int
        """
        distance = self._distance(self.id, key)
        bucketIndex = int(math.log(distance, 2))
        return bucketIndex
    
    def _getContact(self, contactID):
        """ Returns the (known) contact with the specified node ID """
        bucketIndex = self._kbucketIndex(contactID)
        self._buckets[bucketIndex].getContact(contactID)
