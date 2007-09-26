#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

class Contact(object):
    def __init__(self, id, ipAddress, udpPort, firstComm=0):
        self.id = id
        self.address = ipAddress
        self.port = udpPort
        self.commTime = firstComm
        
    def __eq__(self, other):
        if isinstance(other, Contact):
            return self.id == other.id
        else:
            return False
    
    def __ne__(self, other):
        if isinstance(other, Contact):
            return self.id != other.id
        else:
            return True
