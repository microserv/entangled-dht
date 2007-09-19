#!/usr/bin/env python
#
# License: To be determined
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import kademlia.constants

class KBucket:
    def __init__(self):
        self._contacts = dict()

    def addContact(self, contact):
        """ Add contact to _contact dictionary in the right order.

        @return: True if contact added otherwise return false 
        @rtype: bool
        """
        # check to see if there is space to add new contact
        # if there is - add to the bottom of dict
        currentLength = len(self._contacts)
        if currentLength < kademlia.constants.k:
            self._contacts[currentLength+1] = contact
        else:
            # check to see if the first contact in dict is still alive
            result = rpc_ping(self._contacts[1])

            if not result:
                position = 2
                while position <= kademlia.constants.k:
                    self._contacts[position-1] = self._contact[position]
                    position += 1

                self._contacts[kademlia.constants.k] = contact
            else:
                return False

        return True

    def getContacts(self, count):
        pass

