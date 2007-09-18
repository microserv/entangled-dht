#!/usr/bin/env python
#
# License: To be determined
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

class Contact:
    def __init__(self, id, ipAddress, udpPort):
        self.id = id
        self.address = ipAddress
        self.port = udpPort
