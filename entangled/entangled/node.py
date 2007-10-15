#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from twisted.internet import defer

import kademlia.node
from kademlia.node import rpcmethod

class Node(kademlia.node.Node):
    """ Entangled DHT node
    
    This is basically a Kademlia node, but with a few more (non-standard, but
    useful) RPCs defined.
    """
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
