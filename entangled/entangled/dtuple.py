#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import cPickle, hashlib, random

from twisted.internet import defer

from kademlia.node import rpcmethod
from node import EntangledNode

class DistributedTupleSpacePeer(EntangledNode):
    """ A specialized form of an Entangled DHT node that provides an API
    for participating in a distributed Tuple Space (aka Object Space)
    """
    def __init__(self, id=None, udpPort=4000, dataStore=None, routingTable=None, networkProtocol=None):
        EntangledNode.__init__(self, id, udpPort, dataStore, routingTable, networkProtocol)
        self._blockingGetRequests = {}
        self._blockingReadRequests = {}

    def put(self, dTuple, originalPublisherID=None):
        """ Produces a tuple, and writes it into tuple space
        
        @note: This method is generally called "out" in tuple space literature,
               but is renamed to "put" in this implementation to match the 
               renamed "in"/"get" method (see the description for C{get()}).
        
        @param dTuple: The tuple to write into the distributed tuple space (it
                       is named "dTuple" to avoid a conflict with the Python
                       C{tuple} data type).
        @type dTuple: tuple
        
        @rtype: twisted.internet.defer.Deferred
        """
        
        # Look for any active listener tuples for the tuple we're about to publish
        listenerNodeID = []
        listenerKey = []
        
        def publishToTupleSpace(result):
            if result != 'get':
                # Extract "keywords" from the tuple
                subtupleKeys = self._keywordHashesFromTuple(dTuple)
                # Write the tuple to the DHT Tuple Space...
                h = hashlib.sha1()
                tupleValue = cPickle.dumps(dTuple)
                h.update('tuple:' + tupleValue)
                mainKey = h.digest()
                self.iterativeStore(mainKey, tupleValue, originalPublisherID=originalPublisherID)
                # ...and now make it searchable, by writing the subtuples
                df = self._addToInvertedIndexes(subtupleKeys, mainKey)
                return df
        
        def sendTupleToNode(nodes):
            if listenerNodeID[0] in nodes:
                contact = nodes[nodes.index(listenerNodeID[0])]
                df = contact.receiveTuple(listenerKey[0], cPickle.dumps(dTuple))
                return df
        
        def checkIfListenerExists(result):
            if result != None:
                # The result will have a node ID and main listener tuple's key concatenated
                listenerNodeID.append(result[:20]) # 160 bits
                listenerKey.append(result[20:])
                # Another node is waiting for this tuple; we will send it the tuple directly
                listenerNodeID.append(listenerNodeID[0])
                # First remove the listener from the Tuple Space
                self.iterativeDelete(listenerKey[0])
                subtupleKeys = self._keywordHashesFromTuple(dTuple, True)
                self._removeFromInvertedIndexes(subtupleKeys, result)
                # ...now retrieve the contact for the target Node ID, and send it the tuple
                #TODO: perhaps ping this node to make sure its still active
                try:
                    #TODO: verify whether using this method is still valid
                    contact = self._routingTable.getContact(listenerNodeID[0])
                except ValueError:
                    df = self.iterativeFindNode(listenerNodeID[0])
                    df.addCallback(sendTupleToNode)
                    df.addCallback(publishToTupleSpace)
                else:
                    #TODO: add a callback to this to determine if it was a read/get
                    df = contact.receiveTuple(listenerKey[0], cPickle.dumps(dTuple))
                    df.addCallback(publishToTupleSpace)
            else:
                # Extract "keywords" from the tuple
                subtupleKeys = self._keywordHashesFromTuple(dTuple)
                # Write the tuple to the DHT Tuple Space...
                h = hashlib.sha1()
                tupleValue = cPickle.dumps(dTuple)
                h.update('tuple:' + tupleValue)
                mainKey = h.digest()
                def putToSearchIndexes(result):
                    df = self._addToInvertedIndexes(subtupleKeys, mainKey)
                    return df
                
                df = self.iterativeStore(mainKey, tupleValue, originalPublisherID=originalPublisherID)
                df.addCallback(putToSearchIndexes)
                # ...and now make it searchable, by writing the subtuples
                #df = self._addToInvertedIndexes(subtupleKeys, mainKey)
            return df

        df = self._findKeyForTemplate(dTuple, listener=True)
        df.addCallback(checkIfListenerExists)
        return df

    def get(self, template):
        """ Reads and removes (consumes) a tuple from the tuple space (blocking)
        
        @type template: tuple
        
        @note: This method is generally called "in" in tuple space literature,
               but is renamed to "get" in this implementation to avoid
               a conflict with the Python C{in} keyword.
        """
        outerDf = defer.Deferred()
        def addListener(result):
            if result == None:
                # The tuple does not exist (yet) - add a listener for it
                h = hashlib.sha1()
                listenerKey = 'listener:' + cPickle.dumps(template)
                h.update(listenerKey)
                listenerKey = h.digest()
                # Extract "listener keywords" from the template
                subtupleKeys = self._keywordHashesFromTemplate(template, True)
                # ...now write the listener tuple(s) to the DHT Tuple Space
                if subtupleKeys == None:
                    # Deterministic template; all values are fully specified   
                    self.iterativeStore(listenerKey, self.id + listenerKey)
                else:
                    self._addToInvertedIndexes(subtupleKeys, self.id + listenerKey)
                self._blockingGetRequests[listenerKey] = outerDf
            else:
                outerDf.callback(result)

        df = self.getIfExists(template)
        df.addCallback(addListener)
        return outerDf

    def getIfExists(self, template, getListenerTuple=False):
        """ Reads and removes (consumes) a tuple from the tuple space (non-blocking)
        
        @type template: tuple
        
        @param getListenerTuple: If set to True, look for a I{listener tuple}
                                 for this template; this is typically used
                                 to remove event handlers.
        @type getListenerTuple: bool
        
        @note: This method is generally called "in" in tuple space literature,
               but is renamed to "get" in this implementation to avoid
               a conflict with the Python C{in} keyword.
        """
        outerDf = defer.Deferred()
        
        mainTupleKey = []
        def retrieveTupleValue(tupleKey):
            if tupleKey == None:
                # No tuple was found
                outerDf.callback(None)
            else:
                mainTupleKey.append(tupleKey)
                # We use the find algorithm directly so that kademlia does not replicate the key
                if tupleKey in self._dataStore:
                    _df = defer.Deferred()
                    _df.callback({tupleKey: self._dataStore[tupleKey]})
                else:
                    _df = self._iterativeFind(tupleKey, rpc='findValue')
                _df.addCallback(returnTuple)
          
        def returnTuple(value):
            if type(value) == dict:
                # tuple was found
                tupleValue = value[mainTupleKey[0]]
                # Remove the tuple itself from the DHT
                self.iterativeDelete(mainTupleKey[0])
                # Un-serialize the tuple...
                dTuple = cPickle.loads(tupleValue)
                # ...now remove all inverted index entries of the tuple, and return
                subtupleKeys = self._keywordHashesFromTuple(dTuple)
                self._removeFromInvertedIndexes(subtupleKeys, mainTupleKey[0])
                outerDf.callback(dTuple)
            else:
                # tuple was not found
                outerDf.callback(None)

        df = self._findKeyForTemplate(template, getListenerTuple)
        df.addCallback(retrieveTupleValue)
        
        return outerDf
    
    def read(self, template, numberOfResults=1):
        """ Non-destructively reads a tuple in the tuple space (blocking)
        
        This operation is similar to "get" (or "in") in that the peer builds a
        template and waits for a matching tuple in the tuple space. Upon
        finding a matching tuple, however, it copies it, leaving the original
        tuple in the tuple space.
        
        @note: This method is named "rd" in some other implementations.
        
        @param numberOfResults: The maximum number of matching tuples to return.
                                If set to 1 (default), return the tuple itself,
                                otherwise return a list of tuples. If set to 0
                                or lower, return all results.
        @type numberOfResults: int
        
        @return: a matching tuple, or list of tuples (if C{numberOfResults} is
                 not set to 1, or None if no matching tuples were found
        @rtype: twisted.internet.defer.Deferred
        """
        outerDf = defer.Deferred()
        def addListener(result):
            if result == None:
                # The tuple does not exist (yet) - add a listener for it
                h = hashlib.sha1()
                listenerKey = 'listener:' + cPickle.dumps(template)
                h.update(listenerKey)
                listenerKey = h.digest()
                # Extract "listener keywords" from the template
                subtupleKeys = self._keywordHashesFromTemplate(template, True)
                # ...now write the listener tuple(s) to the DHT Tuple Space
                if subtupleKeys == None:
                    # Deterministic template; all values are fully specified   
                    self.iterativeStore(listenerKey, self.id + listenerKey)
                else:
                    self._addToInvertedIndexes(subtupleKeys, self.id + listenerKey)
                # Store the <numberOfResults> parameter as well, in order to return the correct type later (list of tuples vs single tuple)
                self._blockingReadRequests[listenerKey] = (outerDf, numberOfResults)
            else:
                outerDf.callback(result)
        
        df = self.readIfExists(template, numberOfResults=numberOfResults)
        df.addCallback(addListener)
        return outerDf
    
    def readIfExists(self, template, numberOfResults=1):
        """ Non-destructively reads a tuple in the tuple space (non-blocking)
        
        This operation is similar to "get" (or "in") in that the peer builds a
        template and waits for a matching tuple in the tuple space. Upon
        finding a matching tuple, however, it copies it, leaving the original
        tuple in the tuple space.
        
        @note: This method is named "rd" in some other implementations.
        
        @param numberOfResults: The maximum number of matching tuples to return.
                                If set to 1 (default), return the tuple itself,
                                otherwise return a list of tuples. If set to 0
                                or lower, return all results.
        @type numberOfResults: int
        
        @return: a matching tuple, or list of tuples (if C{numberOfResults} is
                 not set to 1, or None if no matching tuples were found
        @rtype: twisted.internet.defer.Deferred
        """
        outerDf = defer.Deferred()
        mainTuplesKeys = [] # list of key IDs that point to matching tuples
        mainTuplesKeysIndex = [-1]
        returnValue = []

        def returnTuple(value):
            if type(value) == dict:
                # Tuple was found
                tupleValue = value[mainTuplesKeys[mainTuplesKeysIndex[0]]]
                # Un-serialize the tuple
                dTuple = cPickle.loads(tupleValue)
                returnValue.append(dTuple)
            if mainTuplesKeysIndex[0] >= len(mainTuplesKeys)-1 or len(returnValue) == numberOfResults:
                if len(returnValue) > 0:
                    if numberOfResults == 1:
                        # return tuple only (not in a list)
                        outerDf.callback(returnValue[0])
                    else:
                        # return all requested results as a list
                        outerDf.callback(returnValue)
                else:
                    # No matching tuples were found
                    outerDf.callback(None)
            else:
                # get the next found tuple
                getNextTuple()

        def retrieveTupleValue(tupleKeys):
            if tupleKeys == None:
                # No matching tuples were found
                outerDf.callback(None)
            else:
                if numberOfResults == 1:
                    mainTuplesKeys.append(tupleKeys)
                else:
                    mainTuplesKeys.extend(tupleKeys)
                print 'mainTuplesKeys:',mainTuplesKeys
                getNextTuple()
                
        def getNextTuple():
            """ Retrieves the next tuple from the C{mainTuplesKeys} list """
            print 'getNextTuple() called'
            mainTuplesKeysIndex[0] += 1
            _df = self.iterativeFindValue(mainTuplesKeys[mainTuplesKeysIndex[0]])
            _df.addCallback(returnTuple)

        df = self._findKeyForTemplate(template, oneResultOnly=(numberOfResults==1))
        df.addCallback(retrieveTupleValue)
        return outerDf

    def _findKeyForTemplate(self, template, listener=False, oneResultOnly=True):
        """ Main search algorithm for C{get()} and C{read()}
        
        @param oneResultOnly: Controls whether one tuple or a list of matching
                              tuples are returned. If C{True} (default),
                              return only one tuple; if C{False}, return all 
                              matching tuples in a list.
        @type oneResultOnly: bool
        
        @return: Immediately returns a deferred object which will be a matching
                 tuple (or list of tuples, depending on the value of
                 C{firstResultOnly}), or C{None} if no matching tuples were
                 found.
        @rtype: twisted.internet.defer.Deferred
        """
        if listener == True:
            prependStr = 'listener:'
        else:
            prependStr = 'tuple:'
        # Prepare a deferred result for this operation
        outerDf = defer.Deferred()
        if listener == True:
            subtupleKeys = self._keywordHashesFromTuple(template, listener)
        else:
            subtupleKeys = self._keywordHashesFromTemplate(template, listener)
    
        kwIndex = [-1] # using a list for this counter because Python doesn't allow binding a new value to a name in an enclosing (non-global) scope
        havePossibleMatches = [False]
        filteredResults = []
        
        listenerResults = []
        listenerSubtupleSetCounter = [0]
        
        #TODO: If all elements in the template are None, we only have the tuple length... maybe raise an exception?
        
        def filterResult(result):
            kwKey = subtupleKeys[kwIndex[0]]
            if type(result) == dict:
                # Value was found; this should be list of keys for tuples matching this criterion
                index = result[kwKey]
                if havePossibleMatches[0] == False:
                    havePossibleMatches[0] = True
                    filteredResults.extend(index)
                else:
                    # Filter the our list of possible matching tuples with the new results
                    delKeys = []
                    for tupleKey in filteredResults:
                        if tupleKey not in index:
                            delKeys.append(tupleKey)
                    for tupleKey in delKeys:
                        filteredResults.remove(tupleKey)
                if len(filteredResults) == 0:
                    # No matches for this template exist at this point; there is no use in searching further
                    outerDf.callback(None)
                else:
                    findNextSubtuple()
            else:
                # Value wasn't found; thus no matches for this template exist - stop the search
                outerDf.callback(None)
                
        def filterListenerResult(result):
            """ Same as filterResult(), except that 2 sets of subtuples keys' results are OR'ed """
            if kwIndex[0] == -1:
                # This was the deterministic search
                if type(result) == dict:
                    # An exact template match was found, callback with this
                    outerDf.callback(result[mainKey])
                else:
                    # The deterministic search did not find anything; start searching subtuples
                    findNextSubtuple()
                return
            
            kwKey = subtupleKeys[kwIndex[0]]
            
            if type(result) == dict:
                # Value was found; this should be list of keys for tuples matching this criterion
                index = result[kwKey]
                listenerResults.extend(index)
            listenerSubtupleSetCounter[0] += 1
               
            if listenerSubtupleSetCounter[0] == 3:
                if havePossibleMatches[0] == False:
                    havePossibleMatches[0] = True
                    filteredResults.extend(listenerResults)
                else:
                    # Filter the our list of possible matching tuples with the new results
                    delKeys = []
                    for tupleKey in filteredResults:
                        if tupleKey not in listenerResults:
                            delKeys.append(tupleKey)
                    for tupleKey in delKeys:
                        try:
                            filteredResults.remove(tupleKey)
                        except ValueError:
                            pass

                if len(filteredResults) == 0:
                    # No matches for this template exist at this point; there is no use in searching further
                    outerDf.callback(None)
                else:
                    # Reset the cycle
                    listenerSubtupleSetCounter[0] = 0
                    while len(listenerResults):
                        listenerResults.pop()
                    findNextSubtuple()
            else:
                findNextSubtuple()
        
        def findNextSubtuple(results=None):
            kwIndex[0] += 1
            if kwIndex[0] < len(subtupleKeys):
                kwKey = subtupleKeys[kwIndex[0]]
                #TODO: kademlia is going to replicate the un-updated inverted index; stop that from happening!!
                df = self.iterativeFindValue(kwKey)
                if listener == True:
                    df.addCallback(filterListenerResult)
                else:
                    df.addCallback(filterResult)
            else:
                # We're done. Let the caller of the parent method know,
                # and return the key of a random qualifying tuple in the list of results
                # (or the entire list of keys, depending on the value of <firstResultOnly>)
                if oneResultOnly == True:
                    print '   _findKeyForTemplate(): returning single random result'
                    outerDf.callback( filteredResults[random.randint(0, len(filteredResults)-1)] )
                else:
                    print '   _findKeyForTemplate(): return result list'
                    outerDf.callback(filteredResults)
        
        if subtupleKeys == None:
            # The template is deterministic; thus we can retrieve the corresponding tuple directly
            h = hashlib.sha1()
            tupleValue = cPickle.dumps(template)
            h.update(prependStr + tupleValue)
            mainKey = h.digest()
            outerDf.callback(mainKey)
        else:
            if listener == True:
                # First look for an exact match if we are looking for listener tuples
                h = hashlib.sha1()
                tupleValue = cPickle.dumps(template)
                h.update(prependStr + tupleValue)
                mainKey = h.digest()
                df = self.iterativeFindValue(mainKey)
                df.addCallback(filterListenerResult)
            else:
                # Query the DHT for the first subtuple (this implicitly specifies the requested tuple length as well)
                findNextSubtuple()
        
        return outerDf
    
    def _keywordHashesFromTuple(self, dTuple, listener=False):
        if listener == True:
            prependStr = 'listener:'
        else:
            prependStr = 'tuple:'
        subtupleKeys = []
        i = 0
        tupleLength = len(dTuple)
        for element in dTuple:
            # Because a tuple is immutable, the position of an element in the tuple
            # is a constant, along with the length of the tuple.
            # This causes each element in the tuble to have two identifiying subtuples (or "keywords")
            # which can be published to the DHT: tuple_length+position+data_type and tuple_length+position+data_value
            # (data_type is implicitly given by data_value)
            #TODO: with the current scheme, it is possible (but unlikely) that an ACTUAL tuple may clash with one of these subtuples
            typeSubtuple = (tupleLength, i, type(element))
            h = hashlib.sha1()
            h.update(prependStr + cPickle.dumps(typeSubtuple))
            subtupleKeys.append(h.digest())
            valueSubtuple = (tupleLength, i, element)
            h = hashlib.sha1()
            h.update(prependStr + cPickle.dumps(valueSubtuple))
            subtupleKeys.append(h.digest())
            wildcardSubtuple = (tupleLength, i, None)
            h = hashlib.sha1()
            h.update(prependStr + cPickle.dumps(wildcardSubtuple))
            subtupleKeys.append(h.digest())
            i += 1
        return subtupleKeys
    
    def _keywordHashesFromTemplate(self, template, listener=False):
        if listener == True:
            prependStr = 'listener:'
        else:
            prependStr = 'tuple:'
        subtupleKeys = []
        i = 0
        tupleLength = len(template)
        deterministicElementCount = 0
        for element in template:
            # See the description in _keywordHashesFromTuple() for how these "keyword" subtuples are constructed
            #if element != None:
                # This element in the template describes the element's value or type
            if type(element) != type and element != None:
                deterministicElementCount += 1
            subtuple = (tupleLength, i, element)
            h = hashlib.sha1()
            h.update(prependStr + cPickle.dumps(subtuple))
            subtupleKeys.append(h.digest())
            #else:
                # The element is None; treat it as a wildcard
            #    pass
            i += 1
        if deterministicElementCount == tupleLength:
            # All of the elements are fully specified in this template; thus we can retrieve the corresponding tuple directly
            return None
        else:
            return subtupleKeys

    @rpcmethod
    def receiveTuple(self, listenerKey, pickledTuple):
        if listenerKey in self._blockingGetRequests:
            dTuple = cPickle.loads(pickledTuple)
            df = self._blockingGetRequests[listenerKey]
            df.callback(dTuple)
            return 'get'
        elif listenerKey in self._blockingReadRequests:
            dTuple = cPickle.loads(pickledTuple)
            df, numberOfResults = self._blockingReadRequests[listenerKey]
            # If the <numberOfResults> paramter in the original read() call was != 1, the caller is expecting a list, not a single tuple
            if numberOfResults == 1:
                df.callback(dTuple)
            else:
                df.callback([dTuple])
            return 'read'
        

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print 'Usage:\n%s UDP_PORT  [KNOWN_NODE_IP  KNOWN_NODE_PORT]' % sys.argv[0]
        print 'or:\n%s UDP_PORT  [FILE_WITH_KNOWN_NODES]' % sys.argv[0]
        print '\nIf a file is specified, it should containg one IP address and UDP port\nper line, seperated by a space.'
        sys.exit(1)
    try:
        int(sys.argv[1])
    except ValueError:
        print '\nUDP_PORT must be an integer value.\n'
        print 'Usage:\n%s UDP_PORT  [KNOWN_NODE_IP  KNOWN_NODE_PORT]' % sys.argv[0]
        print 'or:\n%s UDP_PORT  [FILE_WITH_KNOWN_NODES]' % sys.argv[0]
        print '\nIf a file is specified, it should contain one IP address and UDP port\nper line, seperated by a space.'
        sys.exit(1)

    if len(sys.argv) == 4:
        knownNodes = [(sys.argv[2], int(sys.argv[3]))]
    elif len(sys.argv) == 3:
        knownNodes = []
        f = open(sys.argv[2], 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            ipAddress, udpPort = line.split()
            knownNodes.append((ipAddress, int(udpPort)))
    else:
        knownNodes = None

    node = DistributedTupleSpacePeer( udpPort=int(sys.argv[1]) )
    node.joinNetwork(knownNodes)
    twisted.internet.reactor.run()
