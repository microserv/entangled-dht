#!/usr/bin/env python
#
# License: To be determined
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import kademlia.constants

# remove when protocol in place
pingResult = False

class KBucket:
    def __init__(self):
        self._contacts = list()

    def addContact(self, contact):
        """ Add contact to _contact list in the right order.

        @note: Will need to fix up when protocol up and running
        
        @param contact: The contact to add
        @type contact: kademlia.contact.Contact

        @return: True if contact added otherwise return false 
        @rtype: bool
        """

        # check to see if there is space to add new contact
        # if there is - add to the bottom
        if len(self._contacts) < kademlia.constants.k:
            self._contacts.append(contact)
        else:
            # check to see if the first contact in dict is still alive
            # replace this function when needed
            result = rpc_ping(self._contacts[0])

            if not result:
                # first contact did not respond - remove and add new contact
                self._contacts.remove(self._contacts[0])
                self._contacts.append(contact)
            else:
                # first contact responded, now add to bottom
                tmpContact = self._contacts[0]
                self._contacts.remove(tmpContact)
                self._contacts.append(tmpContact)
                
                # No space
                return False

        # everything went smoothly
        return True

    def getContacts(self, count):
        """ Returns a list containing up to the first count number of contacts
        
        @param count: The amount of contacts to return
        @type count: int
        
        @return: Return up to the first count number of contacts in a list/tuple
                If no contacts are present a null-list is returned
        @rtype: list
        """
        # Get current contact number
        currentLen = len(self._contacts)

        # If count greater than k - return only k contacts
        # !!VERIFY!! behaviour
        if count > kademlia.constants.k:
            count = kademlia.constants.k

        # Check if count value in range and,
        # if count number of contacts are available
        if not currentLen:
            contactList = list()
        # length of list less than requested amount
        elif currentLen < count:
            contactList = self._contacts[0:currentLen]
        # enough contacts in list
        else:
            contactList = self._contacts[0:count]

        return contactList

    def removeContact(self, index):
        """ Remove given contact from list
        
        @return: Return true if operation successful else return false
        @rtype: bool
        """

        # Check to see if index is valid
        if index > kademlia.constants.k-1 or index > len(self._contacts)-1:
            return False
        # Remove contact
        else:
            tmpContact = self._contacts[index]
            self._contacts.remove(tmpContact)
            return True


def rpc_ping(contact):
    return pingResult

