#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import constants

class KBucket:
    """ Description - later
    """
    def __init__(self):
        self._contacts = list()

    def addContact(self, contact):
        """ Add contact to _contact list in the right order.

        @note: Will need to fix up when protocol up and running
        
        @param contact: The contact to add
        @type contact: kademlia.contact.Contact
        """

        #check to see if contact in bucket already
        for tmpContact in self._contacts:
            if tmpContact.id == contact.id:        # Use ids - better way?
                self._contacts.remove(tmpContact)
                self._contacts.append(contact)
                return

        # check to see if there is space to add new contact
        # if there is - add to the bottom
        if len(self._contacts) < kademlia.constants.k:
            self._contacts.append(contact)
        else:
            raise BucketFull("No space in bucket to insert contact")


    def getContacts(self, count):
        """ Returns a list containing up to the first count number of contacts
        
        @param count: The amount of contacts to return
        @type count: int
        @raise IndexError: If the number of requested contacts is too large
        @return: Return up to the first count number of contacts in a list
                If no contacts are present a null-list is returned
        @rtype: list
        """
        # Return all contacts in bucket
        if count == "ALL":
            count = len(self._contacts)

        # Get current contact number
        currentLen = len(self._contacts)

        # If count greater than k - return only k contacts
        # !!VERIFY!! behaviour
        if count > kademlia.constants.k:
            count = kademlia.constants.k
            raise IndexError('Count value too big adjusting to bucket size')

        # Check if count value in range and,
        # if count number of contacts are available
        if not currentLen:
            contactList = list()
            raise BucketEmpty('No contacts in bucket')

        # length of list less than requested amount
        elif currentLen < count:
            contactList = self._contacts[0:currentLen]
        # enough contacts in list
        else:
            contactList = self._contacts[0:count]

        return contactList

    def removeContact(self, index):
        """ Remove given contact from list
        
        @param index: Remove contact in this position from the bucket
        @type index: Integer
        @raise IndexError: If index value too large or not enough contacts are present in the bucket
        """

        # Check to see if index is valid
        if index > kademlia.constants.k-1: # This may never occur - remove check?
            raise IndexError('Specified index greater than bucket length')
            return
        if index > len(self._contacts)-1:
            raise IndexError('Specified index greater than the number of current contacts')
            return

        # Remove contact
        tmpContact = self._contacts[index]
        self._contacts.remove(tmpContact)


class BucketFull(Exception):
    """ BucketFull exception is raised when the bucket is full
    
        This exception will most probably be raised in addContact()
    """
    def __init__(self, message):
        self.message = message

class BucketEmpty(Exception):
    """ BucketEmpty exception is raised when the bucket is empty
    
        This exception will most probably be raised in getContacts()
    """
    def __init__(self, message):
        self.message = message
