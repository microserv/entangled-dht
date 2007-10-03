#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import hashlib, random, math, time

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
    def __init__(self, dataStore=None, networkProtocol=None):
        """ constructor
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
            self._dataStore = datastore.DictDataStore()
        else:
            self._dataStore = dataStore
        #self._pendingContactReplacements = {}

    def joinNetwork(self, udpPort=81172, knownNodeAddresses=None):
        """ Causes the Node to join the Kademlia network; this will execute
        the Twisted reactor's main loop
        
        @param knownNodeAddresses: A sequence of tuples containing IP address
                                   information for existing nodes on the
                                   Kademlia network, in the format:
                                   C{(<ip address>, (udp port>)}
        @type knownNodeAddresses: tuple
        """
        # Prepare the underlying Kademlia protocol
        protocol.reactor.listenUDP(udpPort, self._protocol)
        # Create temporary contact information for the list of addresses of known nodes
        if knownNodeAddresses != None:
            bootstrapContacts = []
            for address, port in knownNodeAddresses:
                contact = Contact(self._generateID(), address, port, self._protocol)
                bootstrapContacts.append(contact)
        else:
            bootstrapContacts = None
        # Initiate the Kademlia joining sequence - perform a search for this node's own ID
        df = self._iterativeFind(self.id, bootstrapContacts)
        # Refresh all k-buckets further away than this node's closest neighbour
        def getBucketAfterNeighbour(*args):
            for i in range(160):
                if len(self._buckets[i]) > 0:
                    return i+1
            return 160
        df.addCallback(getBucketAfterNeighbour)
        df.addCallback(self._refreshKBuckets)
        protocol.reactor.callLater(30, self.printContacts)
        # Start refreshing k-buckets periodically, if necessary
        protocol.reactor.callLater(constants.checkRefreshInterval, self._refreshNode)
        protocol.reactor.run()


    def printContacts(self):
        contacts = self._findCloseNodes(self.id, 100)
        print '\n\nNODE CONTACTS\n==============='
        for item in contacts:
            print item
        print '=================================='
        protocol.reactor.callLater(30, self.printContacts)


    def iterativeStore(self, key, value, originalPublisherID=None, age=0):
        """ The Kademlia store operation """
        if originalPublisherID == None:
            originalPublisherID = self.id
        # Prepare a callback for doing "STORE" RPC calls
        def executeStoreRPCs(nodes):
            for contact in nodes:
                contact.store(key, value, originalPublisherID, age)
        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key)
        # ...and send them STORE RPCs as soon as they've been found
        df.addCallback(executeStoreRPCs)
    
    def iterativeFindNode(self, key):
        """ The basic Kademlia node lookup operation """
        return self._iterativeFind(key)
    
    def iterativeFindValue(self, key):
        """ The Kademlia search operation """
        # Prepare a callback for this operation
        outerDf = defer.Deferred()
        def checkResult(result):
            if type(result) == dict:
                # We have found the value; now see who was the closest contact without it...
                if 'closestNodeNoValue' in result:
                    # ...and store the key/value pair 
                    contact = result['closestNodeNoValue']
                    contact.store(key, value)
            else:
                # The value wasn't found, but a list of contacts was returned
                #TODO: should we do something with this? -since our own routing table would have been updated automatically...
                pass
            outerDf.callback(result)
        # Execute the search
        df = self._iterativeFind(key, findValue=True)
        df.addCallback(checkResult)
        return outerDf
    
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
            headContact = self._buckets[bucketIndex]._contacts[0]
            
            def replaceContact(self, failure):
                """ @type failure: twisted.python.failure.Failure """
                failure.trap(protocol.TimeoutError)
                contactID = failure.getErrorMessage()
                # Remove the old contact...
                bucketIndex = self._kbucketIndex(contactID)
                self._buckets[bucketIndex].remove(contactID)
                # ...and add the new one at the tail of the bucket
                self.addContact(contact)
            
            # Ping the least-recently seen contact in this k-bucket
            headContact = self._buckets[bucketIndex]._contacts[0]
            df = headContact.ping()
            #self._pendingContactReplacements[headContact.id] = contact
            # If there's an error (i.e. timeout), remove the head contact, and append the new one
            df.addErrback(replaceContact)
    
    def removeContact(self, contactID):
        """ Remove the contact with the specified node ID from this node's
        table of known nodes
        
        @param contactID: The node ID of the contact to remove
        @type contactID: str
        
        @raise ValueError: Raised if the contact isn't found
        """
        bucketIndex = self._kbucketIndex(contactID)
        try:
            self._buckets[bucketIndex].removeContact(contactID)
        except ValueError, e:
            print 'removeContact(): Warning: ', e
            raise

    @rpcmethod
    def ping(self):
        """ Used to verify contact between two Kademlia nodes """
        return 'pong'

    @rpcmethod
    def store(self, key, value, originalPublisherID=None, age=0, **kwargs):
        """ Store the received data in the local hash table
        
        @param key: The hashtable key of the data
        @type key: str
        @param value: The actual data (the value associated with C{key})
        @type value: str
        @param originalPublisherID: The node ID of the node that is the
                                    B{original} publisher of the data
        @type originalPublisherID: str
        @param age: The relative age of the data (time in seconds since it was
                    originally published). Note that the original publish time
                    isn't actually given, to compensate for clock skew between
                    different nodes.
        @type age: int
        
        @todo: Since the data (value) may be large, passing it around as a buffer
               (which is the case currently) might not be a good idea... will have
               to fix this (perhaps use a stream from the Protocol class?)
        """
        # Get the sender's ID (if any)
        if '_rpcNodeID' in kwargs:
            rpcSenderID = kwargs['_rpcNodeID']
        else:
            rpcSenderID = None
            
        if originalPublisherID == None:
            if rpcSenderID != None:
                originalPublisherID = rpcSenderID
            else:
                raise TypeError, 'No publisher specifed, and RPC caller ID not available. Data requires an original publisher.'

        now = time.time()
        originallyPublished = now - age
        self._dataStore.setItem(key, value, now, originallyPublished, originalPublisherID)

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
        contacts = self._findCloseNodes(key, constants.k, rpcSenderID)
        contactTriples = []
        for contact in contacts:
            contactTriples.append( (contact.id, contact.address, contact.port) )
        return contactTriples

    @rpcmethod
    def findValue(self, key, **kwargs):
        """ Return the value associated with the specified key if present in
        this node's data, otherwise execute FIND_NODE for the key
        
        @param key: The hashtable key of the data to return
        @type key: str
        """
        if key in self._dataStore:
            return {key: self._dataStore[key]}
        else:
            return self.findNode(key, **kwargs)

    def _distance(self, keyOne, keyTwo):
        """ Calculate the XOR result between two string variables
        
        @return: XOR result of two long variables
        @rtype: long
        """
        valKeyOne = long(keyOne.encode('hex'), 16)
        valKeyTwo = long(keyTwo.encode('hex'), 16)
        return valKeyOne ^ valKeyTwo

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

    def _generateID(self):
        """ Generates a 160-bit pseudo-random identifier
        
        @return: A globally unique 160-bit pseudo-random identifier
        @rtype: str
        """
        hash = hashlib.sha1()
        hash.update(str(random.getrandbits(255)))  
        return hash.digest()
    
    def _getContact(self, contactID):
        """ Returns the (known) contact with the specified node ID """
        bucketIndex = self._kbucketIndex(contactID)
        return self._buckets[bucketIndex].getContact(contactID)
    
    def _iterativeFind(self, key, shortlist=None, findValue=False):
        """ The basic Kademlia iterative lookup operation (for nodes/values)
        
        This builds a list of k "closest" contacts through iterative use of
        the "FIND_NODE" RPC, or if C{findValue} is set to C{True}, using the
        "FIND_VALUE" RPC, in which case the value (if found) may be returned
        instead of a list of contacts
        """
        print '\n_iterativeFind() called'
        if shortlist == None:
            shortlist = self._findCloseNodes(key, constants.alpha)
            if key != self.id:
                # Update the "last accessed" timestamp for the appropriate k-bucket
                bucketIndex = self._kbucketIndex(key)
                self._buckets[bucketIndex].lastAccessed = time.time()
            if len(shortlist) == 0:
                # This node doesn't know of any other nodes
                fakeDf = defer.Deferred()
                fakeDf.callback(None)
                print '...exiting due to no known nodes'
                return fakeDf
            # Note the closest known node
            #TODO: possible IndexError exception here:
            closestNode = [shortlist[0], None] # format: [<current closest node>, <previous closest node>]
            for contact in shortlist:
                if self._distance(key, contact.id) < self._distance(key, closestNode[0].id):
                    closestNode[0] = contact
        else:
            # This is used during the bootstrap process; node ID's are most probably fake
            shortlist = shortlist
            closestNode = [None, None]
            print 'using a bootstrap shortlist:', shortlist
        
        print '\n++++++++ START OF ITERATIVE SEARCH +++++++++'
        # List of contact IDs that have already been queried
        alreadyContacted = []
        # List of active queries; len() indicates number of active probes
        # - using a list for this, because Python doesn't allow binding a new value to a name in an enclosing (non-global) scope
        activeProbes = []
        # A list of known-to-be-active remote nodes
        activeContacts = []
        # This should only contain one entry; the next scheduled iteration call - using a list because of Python's scope-name-binding handling
        pendingIterationCalls = []        
        
        findValueResult = {}
        
        def extendShortlist(responseMsg):
            """ @type responseMsg: kademlia.msgtypes.ResponseMessage """
            #print 'deferred callback to extendShortlist:'
            #print '==========='
            # Mark this node as active
            if responseMsg.nodeID not in activeContacts:
                aContact = self._getContact(responseMsg.nodeID)
                activeContacts.append(aContact)
                if responseMsg.nodeID not in alreadyContacted:
                    # This makes sure "bootstrap"-nodes with "fake" IDs don't get queried twice
                    alreadyContacted.append(responseMsg.nodeID)
                    if closestNode[0] != None:
                        if self._distance(key, responseMsg.nodeID) < self._distance(key, closestNode[0].id):
                            closestNode[0] = self._getContact(responseMsg.nodeID)
                    else:
                        print 'setting closest node to a bootstrap node...'
                        closestNode[0] = self._getContact(responseMsg.nodeID)
                        print '====>closestNode is:', closestNode[0]      
            # Now grow extend the shortlist with the returned contacts
            result = responseMsg.response
            #TODO: some validation on the result (for guarding against attacks)
            print '==> node returned result:',result
            
            # If we are looking for a value, first see if this result is the value
            # we are looking for before treating it as a list of contact triples
            if findValue == True and type(result) == dict:
                # We have found the value
                findValueResult[key] = result[key]
            else:
                if findValue == True:
                    # We are looking for a value, and the remote node didn't have it
                    # - mark it as the closest "empty" node, if it is
                    if 'closestNodeNoValue' in findValueResult:
                        if self._distance(key, responseMsg.nodeID) < self._distance(key, closestNode[0].id):
                            findValueResult['closestNodeNoValue'] = self._getContact(responseMsg.nodeID)
                    else:
                        findValueResult['closestNodeNoValue'] = self._getContact(responseMsg.nodeID)                

                for contactTriple in result:
                    testContact = Contact(contactTriple[0], contactTriple[1], contactTriple[2], self._protocol)
                    #print 'testing for shortlist'
                    if testContact not in shortlist:
                        #TODO: currently, the shortlist can grow to more than k entries... should probably fix this, but it isn't fatal
                        print '....................adding new contact to shortlist:', testContact
                        shortlist.append(testContact)
                        if closestNode[0] != None:
                            if self._distance(key, testContact.id) < self._distance(key, closestNode[0].id):
                                closestNode[0] = testContact
                        else:
                            closestNode[0] = testContact
            return responseMsg.nodeID
        
        def removeFromShortlist(failure):
            """ @type failure: twisted.python.failure.Failure """
            print '=== timeout ==='
            failure.trap(protocol.TimeoutError)
            deadContactID = failure.getErrorMessage()
            if deadContactID in shortlist:
                shortlist.remove(deadContactID)
            return deadContactID  
                
        def cancelActiveProbe(contactID):
            #print '.........probe ending...'
            activeProbes.pop()
            if len(activeProbes) == 0 and len(pendingIterationCalls):
                #print 'forcing iteration'
                # Force the iteration
                pendingIterationCalls[0].cancel()
                del pendingIterationCalls[0]
                searchIteration()
            #print 'probe inactive. count is:', len(activeProbes)

        # Send parallel, asynchronous FIND_NODE RPCs to the shortlist of contacts
        def searchIteration():
            while len(pendingIterationCalls):
                del pendingIterationCalls[0]
            # See if should continue the search
            if key in findValueResult:
                print '++++++++++++++ DONE (findValue found) +++++++++++++++\n\n'
                outerDf.callback(findValueResult[key])
            elif len(activeContacts) >= constants.k or (closestNode[0] == closestNode[1] and closestNode[0] != None):
                # Ok, we're done; either we have accumulated k active contacts or
                # no improvement in closestNode has been noted
                #print 'len(activeContacts):', len(activeContacts)
                #print 'closestNode:', closestNode[0]
                #print 'previousClosestNode:', closestNode[1]
                #print '!!!!!!!ADDING CONTACTS!!!!!!!!!!'
                #for contact in activeContacts:
                #    self.addContact(contact)
                print '++++++++++++++ DONE (test) +++++++++++++++\n\n'
                outerDf.callback(activeContacts)
            else:
                #print 'search continues...'
                #print 'len(activeContacts):', len(activeContacts)
                #print 'closestNode:', closestNode[0]
                #print 'previousClosestNode:', closestNode[1]
                # The search continues...
                contactedNow = 0
                for contact in shortlist:
                    if contact.id not in alreadyContacted:
                        print '...launching probe to:', contact
                        activeProbes.append(contact.id)
                        if findValue == True:
                            df = contact.findValue(key, rawResponse=True)
                        else:
                            df = contact.findNode(key, rawResponse=True)
                        df.addCallback(extendShortlist)
                        df.addErrback(removeFromShortlist)
                        df.addCallback(cancelActiveProbe)
                        alreadyContacted.append(contact.id)
                        contactedNow += 1
                    if contactedNow == constants.alpha:
                        break                    
                closestNode[1] = closestNode[0]
                if contactedNow > 0 or len(activeProbes) > 0:
                    # Schedule the next iteration (Kademlia uses loose parallelism)
                    call = protocol.reactor.callLater(constants.iterativeLookupDelay, searchIteration)
                    pendingIterationCalls.append(call)
                else:
                    print '++++++++++++++ DONE (logically) +++++++++++++\n\n'
                    # If no probes were sent, there will not be any improvement, so we're done
                    outerDf.callback(closestNode[0])
                
        outerDf = defer.Deferred()
        # Start the iterations
        searchIteration()
        return outerDf
    
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
    
    def _randomIDInBucketRange(self, bucketIndex):
        """ Returns a random ID in the specified k-bucket's range
        
        @param bucketIndex: The index of the k-bucket to use
        @type bucketIndex: int
        """
        def makeIDString(distance):
            id = hex(distance)[2:]
            if id[-1] == 'L':
                id = id[:-1]
            if len(id) % 2 != 0:
                id = '0' + id
            id = id.decode('hex')
            id = (20 - len(id))*'\x00' + id
            return id
        min = math.pow(2, bucketIndex)
        max = math.pow(2, bucketIndex+1)
        distance = random.randrange(min, max)
        distanceStr = makeIDString(distance)
        randomID = makeIDString(self._distance(distanceStr, self.id))
        return randomID

    def _refreshKBuckets(self, startIndex=0, force=False):
        """ Refreshes all k-buckets that need refreshing, starting at the
        k-bucket with the specified index

        @param startIndex: The index of the bucket to start refreshing at;
                           this bucket and those further away from it will
                           be refreshed. For example, when joining the
                           network, this node will set this to the index of
                           the bucket after the one containing it's closest
                           neighbour.
        @type startIndex: index
        @param force: If this is C{True}, all buckets (in the specified range)
                      will be refreshed, regardless of the time they were last
                      accessed.
        @type force: bool
        """
        print '_refreshKbuckets called with index:',startIndex
        bucketIndex = []
        bucketIndex.append(startIndex + 1)
        outerDf = defer.Deferred()
        def refreshNextKBucket(dfResult=None):
            print '  refreshNexKbucket called; bucketindex is', bucketIndex[0]
            bucketIndex[0] += 1
            while bucketIndex[0] < 160:
                if force or (time.time() - self._buckets[bucketIndex[0]].lastAccessed >= constants.refreshTimeout):
                    searchID = self._randomIDInBucketRange(bucketIndex[0])
                    self._buckets[bucketIndex[0]].lastAccessed = time.time()
                    print '  refreshing bucket',bucketIndex[0]
                    df = self.iterativeFindNode(searchID)
                    df.addCallback(refreshNextKBucket)
                    return
                else:
                    bucketIndex[0] += 1
            # If this is reached, we have refreshed all the buckets
            print '  all buckets refreshed; initiating outer deferred callback'
            outerDf.callback(None)
        print '_refreshKbuckets starting cycle'
        refreshNextKBucket()
        print '_refreshKbuckets returning'
        return outerDf
    
    def _refreshNode(self):
        """ Periodically called to perform k-bucket refreshes and data
        replication/republishing as necessary """
        print 'refreshNode called'
        df = self._refreshKBuckets(0, False)
        df.addCallback(self._republishData)
        protocol.reactor.callLater(constants.checkRefreshInterval, self._refreshNode)

    def _republishData(self, *args):
        """ Republishes and expires any stored data (i.e. stored
        C{(key, value pairs)} that need to be republished/expired """
        print 'republishData called'
        for key in self._dataStore:
            now = time.time()
            originalPublisherID = self._dataStore.originalPublisherID(key)
            age = now - self._dataStore.originallyPublished(key)
            if originalPublisherID == self.id:
                # This node is the original publisher; it has to republish
                # the data before it expires (24 hours in basic Kademlia)
                if age >= constants.dataExpireTimeout:
                    self.iterativeStore(key, self._dataStore[key])
            else:
                # This node needs to replicate the data at set intervals,
                # until it expires, without changing the metadata associated with it
                if now - self._dataStore.lastPublished(key) >= constants.replicateInterval:
                    self.iterativeStore(key, self._dataStore[key], originalPublisherID, age)

import sys
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'Usage:\n%s UDP_PORT KNOWN_NODE_IP  KNOWN_NODE_PORT' % sys.argv[0]
        sys.exit(1)
    node = Node()
    if len(sys.argv) == 4:
        knownNodes = [(sys.argv[2], int(sys.argv[3]))]
    else:
        knownNodes = None
    node.joinNetwork(int(sys.argv[1]), knownNodes)
