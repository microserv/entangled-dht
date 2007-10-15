#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import hashlib

from twisted.internet import defer

import kademlia.node
from kademlia.node import rpcmethod


class Node(kademlia.node.Node):
    """ Entangled DHT node
    
    This is basically a Kademlia node, but with a few more (non-standard, but
    useful) RPCs defined.
    """
  
    def searchForKeyword(self, keyword):
        """ The Entangled search operation (keyword-based)
        
        Call this to find keys in the DHT which contain the specified
        keyword(s).
        """
        keyword = keyword.lower()
        h = hashlib.sha1()
        h.update(keyword)
        key = h.digest()
        
        def checkResult(result):
            if type(result) == dict:
                # Value was found; this should be list of (real name, key) pairs
                index = result[key]
                sourceListString = ''
                for name, hash in index:
                    print '  .....in for'
                    sourceListString += '%s\n' % name
                result = sourceListString[:-1]
            else:
                # Value wasn't found
                result = ''
            return result
        
        df = self.iterativeFindValue(key)
        df.addCallback(checkResult)
        return df
        
        
    def publishData(self, name, data):
        """ The Entangled high-level data publishing operation
        
        Call this to store data in the Entangled DHT.
        
        @note: This will automatically create a hash of the specified C{name}
        parameter, and add the published data to the appropriate inverted
        indexes, to enable keyword-based searching. If this behaviour is not 
        wanted/needed, rather call the Kademlia base node's
        C{iterativeStore()} method directly.
        """
        h = hashlib.sha1()
        h.update(name)
        mainKey = h.digest()

        # Prepare a deferred result for this operation
        outerDf = defer.Deferred()

        # Create hashes for the keywords in the name
        keywordKeys = []
        splitName = name.lower()
        for splitter in ('_', '.', '/'):
            splitName = splitName.replace(splitter, ' ')
        kwIndex = [-1] # using a list for this counter because Python doesn't allow binding a new value to a name in an enclosing (non-global) scope
        for keyword in splitName.split():
            # Only consider keywords with 3 or more letters
            if len(keyword) >= 3:
                h = hashlib.sha1()
                h.update(keyword)
                key = h.digest()
                keywordKeys.append(key)

        # Store the main key, with its value...
        self.iterativeStore(mainKey, data)
        # ...and now update the inverted indexes (or add them, if they don't exist yet)
        def addToInvertedIndex(results):
            kwKey = keywordKeys[kwIndex[0]]
            if type(results) == dict:
                # An index already exists; add our value to it
                index = results[kwKey]
                #TODO: this might not actually be an index, but a value... do some name-mangling to avoid this
                index.append( (name, mainKey) )
            else:
                # An index does not yet exist for this keyword; create one
                index = [ (name, mainKey) ]
            df = self.iterativeStore(kwKey, index)
            df.addCallback(storeNextKeyword)
        
        def storeNextKeyword(results=None):
            kwIndex[0] += 1
            if kwIndex[0] < len(keywordKeys):
                kwKey = keywordKeys[kwIndex[0]]
                #TODO: kademlia is going to replicate the un-updated inverted index; stop that from happening!!
                df = self.iterativeFindValue(kwKey)
                df.addCallback(addToInvertedIndex)
            else:
                # We're done. Let the caller of the parent method know
                outerDf.callback(None)
             
        if len(keywordKeys) > 0:
            # Start the "keyword store"-cycle
            storeNextKeyword()
            
        return outerDf
    
    def iterativeDelete(self, key):
        """ The Entangled delete operation
        
        Call this to remove data from the DHT.
        
        The Entangled delete operation uses the basic Kademlia node lookup
        algorithm (same as Kademlia's search/retrieve). The algorithm behaves
        the same as when issueing the FIND_NODE RPC - the only difference is
        that the DELETE RPC (defined in C{delete()}) is used instead of
        FIND_NODE.
        
        @param key: The hashtable key of the data
        @type key: str
        """
        # Delete our own copy of the data
        if key in self._dataStore:
            del self._dataStore[key]
        df = self._iterativeFind(key, rpc='delete')
        return df

    @rpcmethod
    def delete(self, key, **kwargs):
        """ Deletes the the specified key (and it's value) if present in
        this node's data, and executes FIND_NODE for the key
        
        @param key: The hashtable key of the data to delete
        @type key: str
        
        @return: A list of contact triples closest to the specified key. 
                 This method will return C{k} (or C{count}, if specified)
                 contacts if at all possible; it will only return fewer if the
                 node is returning all of the contacts that it knows of.
        @rtype: list
        """
        # Delete our own copy of the data (if we have one)...
        if key in self._dataStore:
            del self._dataStore[key]
        # ...and make this RPC propagate through the network (like a FIND_VALUE for a non-existant value)
        return self.findNode(key, **kwargs)


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
