#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import cPickle, hashlib

from twisted.internet import defer

from node import EntangledNode

class DistributedTupleSpacePeer(EntangledNode):
    """ A specialized form of an Entangled DHT node that provides an API
    for participating in a distributed Tuple Space (aka Object Space)
    """
    def put(self, dTuple):
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
#        subtupleKeys = []
#        i = 0
#        tupleLength = len(dTuple)
#        for element in dTuple:
#            # Because a tuple is immutable, the position of an element in the tuple
#            # is a constant, along with the length of the tuple.
#            # This causes each element in the tuble to have two identifiying subtuples (or "keywords")
#            # which can be published to the DHT: tuple_length+position+data_type and tuple_length+position+data_value
#            # (data_type is implicitly given by data_value)
#            #TODO: with the current scheme, it is possible (but unlikely) that an ACTUAL tuple may clash with one of these subtuples
#            typeSubtuple = (tupleLength, i, type(element))
#            h = hashlib.sha1()
#            h.update(cPickle.dumps(typeSubtuple))
#            subtupleKeys.append(h.digest())
#            valueSubtuple = (tupleLength, i, element)
#            h = hashlib.sha1()
#            h.update(cPickle.dumps(valueSubtuple))
#            subtupleKeys.append(h.digest())
#            i += 1
        subtupleKeys = self._keywordHashesFromTuple(dTuple)
        # Write the tuple to the DHT Tuple Space...
        h = hashlib.sha1()
        tupleValue = cPickle.dumps(dTuple)
        h.update(tupleValue)
        mainKey = h.digest()
        self.iterativeStore(mainKey, tupleValue)
        # ...and now make it searchable, by writing the subtuples
        df = self._addToInvertedIndexes(subtupleKeys, mainKey)
        return df
    
    def get(self, template):
        """ Reads and removes (consumes) a tuple from the tuple space.
        
        @type template: tuple
        
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
                #TODO: kademlia is going to replicate the un-updated inverted index; stop that from happening!!
                _df = self.iterativeFindValue(tupleKey)
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

        df = self._findTupleForTemplate(template)
        df.addCallback(retrieveTupleValue)
        return outerDf
    
    def read(self, template):
        """ Non-destructively reads a tuple in the tuple space.
        
        This operation is similar to "get" (or "in") in that the peer builds a
        template and waits for a matching tuple in the tuple space. Upon
        finding a matching tuple, however, it copies it, leaving the original
        tuple in the tuple space.
        
        @note: This method is named "rd" in some other implementations.
        """
        outerDf = defer.Deferred()
        mainTupleKey = []
        def retrieveTupleValue(tupleKey):
            if tupleKey == None:
                # No tuple was found
                outerDf.callback(None)
            else:
                mainTupleKey.append(tupleKey)
                _df = self.iterativeFindValue(tupleKey)
                _df.addCallback(returnTuple)
            
        def returnTuple(value):
            if type(value) == dict:
                # tuple was found
                tupleValue = value[mainTupleKey[0]]
                # Un-serialize the tuple
                dTuple = cPickle.loads(tupleValue)
                outerDf.callback(dTuple)
            else:
                # tuple was not found
                outerDf.callback(None)

        df = self._findTupleForTemplate(template)
        df.addCallback(retrieveTupleValue)
        return outerDf
        
    def _findTupleForTemplate(self, template):
        """ Main search algorithm for C{get()} and C{read()} """
        # Prepare a deferred result for this operation
        outerDf = defer.Deferred()
        subtupleKeys = []
        i = 0
        tupleLength = len(template)
        deterministicElementCount = 0
    
        kwIndex = [-1] # using a list for this counter because Python doesn't allow binding a new value to a name in an enclosing (non-global) scope
        havePossibleMatches = [False]
        filteredResults = []
        
        for element in template:
            # See the description in put() for how these "keyword" subtuples are constructed
#            if type(element) == type:
#                # This element in the template only describes the elment's data type (not value)
#                typeSubtuple = (tupleLength, i, type(element))
#                h = hashlib.sha1()
#                h.update(cPickle.dumps(typeSubtuple))
#                subtupleKeys.append(h.digest())
            #el
            if element != None:
                # This element in the template describes the element's value or type
                if type(element) != type:
                    deterministicElementCount += 1
                subtuple = (tupleLength, i, element)
                h = hashlib.sha1()
                h.update(cPickle.dumps(subtuple))
                subtupleKeys.append(h.digest())
            else:
                # The element is None; treat it as a wildcard
                pass
            i += 1
        
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
        
        def findNextSubtuple(results=None):
            kwIndex[0] += 1
            if kwIndex[0] < len(subtupleKeys):
                kwKey = subtupleKeys[kwIndex[0]]
                #TODO: kademlia is going to replicate the un-updated inverted index; stop that from happening!!
                df = self.iterativeFindValue(kwKey)
                df.addCallback(filterResult)
            else:
                # We're done. Let the caller of the parent method know, and return the key of the first qualifying tuple in the list of results
                outerDf.callback(filteredResults[0])
        
        if deterministicElementCount == tupleLength:
            # All of the elements are fully specified in this template; thus we can retrieve the corresponding tuple directly
            h = hashlib.sha1()
            tupleValue = cPickle.dumps(template)
            h.update(tupleValue)
            mainKey = h.digest()
            outerDf.callback(mainKey)
        else:
            # Query the DHT for the first subtuple (this implicitly specifies the requested tuple length as well)
            findNextSubtuple()
        
        return outerDf
    
    def _keywordHashesFromTuple(self, dTuple):
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
            h.update(cPickle.dumps(typeSubtuple))
            subtupleKeys.append(h.digest())
            valueSubtuple = (tupleLength, i, element)
            h = hashlib.sha1()
            h.update(cPickle.dumps(valueSubtuple))
            subtupleKeys.append(h.digest())
            i += 1
        return subtupleKeys
    