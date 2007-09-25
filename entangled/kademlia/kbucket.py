#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import constants

class BucketFull(Exception):
    """ BucketFull exception is raised when the bucket is full
    """

class BucketEmpty(Exception):
    """ BucketEmpty exception is raised when the bucket is empty
    """

class KBucket:
    """ Description - later
    """
    def __init__(self):
        self._contacts = list()

    def addContact(self, contact):
        """ Add contact to _contact list in the right order.

        @note: Will need to fix up when protocol up and running
        
        @raise kademlia.kbucket.BucketFull: Raised when the bucket is full
        
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
        if len(self._contacts) < constants.k:
            self._contacts.append(contact)
        else:
            raise BucketFull("No space in bucket to insert contact")


    def getContacts(self, count):
        """ Returns a list containing up to the first count number of contacts
        
        @param count: The amount of contacts to return
        @type count: int
        
        @raise IndexError: If the number of requested contacts is too large
        @raise kademlia.kbucket.BucketEmpty: the bucket is empty
        
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
        if count > constants.k:
            count = constants.k
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

    def removeContact(self, contact):
        """ Remove given contact from list
        
        @param contact: The contact to remove
        @type contact: kademlia.contact.Contact
        
        @raise ValueError: The specified contact is not in this bucket
        """
        self._contacts.remove(contact)

