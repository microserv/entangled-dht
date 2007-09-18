#!/usr/bin/env python
#
# License: To be determined
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import hashlib, random

class Node:
    def __init__(self, knownNodes=None):
        self.id = ''
        self._buckets = []
        self._connection = None
        
    def _generateID(self):
        """ Generates a 160-bit pseudo-random identifier
        
        @todo: this code may have to be replaced with the hashing function
               defined by the Chord protocol, as node ID's need to be
               uniformly distributed
       
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
    
    def updateContacts(self, contacts):
        pass

