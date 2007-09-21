#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import hashlib, random

import datastore
import kbucket


class Node:
    def __init__(self, knownNodes=None, dataStore=datastore.DataStore()):
        self.id = self._generateID()
        self._buckets = [] # remove?
        self._connection = None
        self._dataStore = dataStore
        self._kbucket = kbucket.KBucket()

    def _generateID(self):
        """ Generates a 160-bit pseudo-random identifier
        
        @return: A globally unique 160-bit pseudo-random identifier
        @rtype: str
        """
        hash = hashlib.sha1()
        hash.update(str(random.getrandbits(255)))  
        return hash.digest()

    def _lookupNode(self, key):
        pass
    
    def findNode(self, key):
        pass
    
    def updateContact(self, contact):
        """ Update the given contact

        @param contacts: kademlia.contact.Contact 
        @note: It is assumed that the bucket is -
            1) the contact is alive - timeout stuff sorted before method called!
            2) not full
            3) contact is in list

            If the exception is raised then a new contact has arrived
            and then the bucket should be resorted i.e. closest contacts are in bucket
        """
        try:
            self._kbucket.addContact(contact)
        except self._kbucket.BucketFull, e:
            print "Warning: " + e.message()
            updateContacts(contact)

    def updateContacts(self, contact):
        """ Update all current contacts in bucket by sending a ping request to all of them
            Then determine the closest set of contacts
        """
        contactList = self._kbucket.getContacts("ALL")
        for currentContact in contactList:
            # PING(currentContact)
            pass
        
        # COMPARE RTT (round trip time)


    def _distance(self, keyOne, keyTwo):
        """ Calculate the XOR result between two string variables
        
        @return: XOR result of two long variables
        @rtype: long
        """
        valKeyOne = long(keyOne.encode('hex'), 16)
        valKeyTwo = long(keyTwo.encode('hex'), 16)
        return valKeyOne ^ valKeyTwo

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
        
