#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import hashlib, random, math

import constants
import kbucket
import datastore
import protocol

def rpcmethod(func):
    """ Decorator to expose methods as RPC calls """
    func.rpcmethod = True
    return func

class Node(object):
    def __init__(self, knownNodes=None, dataStore=None, networkProtocol=None):
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

    def _iterativeFindNode(self, key):
        """ The basic Kademlia node lookup operation
        
        This builds a list of k "closest" contacts through iterative use of
        the "FIND_NODE" RPC """
        shortlist = self.findNode(key, constants.alpha)
        # Note the closest known node
        #TODO: possible IndexError exception here:
        closestNode = shortlist[0]
        for contact in shortlist:
            if self._distance(key, contact.id) < self._distance(key, closestNode.id):
                closestNode = contact
    
        def extendShortlist(rpcContacts):
            for contact in rpcContacts:
                if contact not in shortlist:
                    shortlist.append(contact)
        
        def removeFromShortlist(errorContact):
            if errorContact in shortlist:
                shortlist.remove(errorContact)
        
        # Send parallel, asynchronous FIND_NODE RPCs to the shortlist of contacts
        alreadyContacted = []
        for contact in shortlist:
            #TODO: add deferred, timeouts - remove from shortlist if timeout
            df = contact.findNode(key)
            df.addErrback(removeFromShortlist)
            df.addCallback(extendShortlist)
            alreadyContacted.append(contact)
                

    
    def findNode(self, key, count=constants.k):
        """ Finds C{k} known nodes closest to the node/value with the
        specified key.
        
        @param key: the 160-bit key (i.e. the node or value ID) to search for
        @type key: str
        @param count: the amount of contacts to return (this defaults to C{k})
        @type count: int
        
        @return: A list of node contacts (C{kademlia.contact.Contact instances})
                 closest to the specified key. 
                 This method will return C{k} (or C{count}, if specified)
                 contacts if at all possible; it will only return fewer if the
                 node is returning all of the contacts that it knows of.
        @rtype: list
        """
        distance = self._distance(self.id, key)
        bucketIndex = int(math.log(distance, 2))
        closestNodes = self._buckets[bucketIndex].getContacts(constants.k)
        # The node must return k contacts, unless it does not know at least 8
        i = 1
        canGoLower = bucketIndex-i >= 0
        canGoHigher = bucketIndex+i < 160
        # Fill up the node list to k nodes, starting with the closest neighbouring nodes known 
        while len(closestNodes) < constants.k and (canGoLower or canGoHigher):
            #TODO: this may need to be optimized
            if canGoLower:
                closestNodes.extend(self._buckets[bucketIndex-i].getContacts(constants.k - len(closestNodes)))
                canGoLower = bucketIndex-(i+1) >= 0
            if canGoHigher:
                closestNodes.extend(self._buckets[bucketIndex+i].getContacts(constants.k - len(closestNodes)))
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
        distance = self._distance(self.id, contact.id)
        bucketIndex = int(math.log(distance, 2))
        
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
        distance = self._distance(self.id, contact.id)
        bucketIndex = int(math.log(distance, 2))
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
