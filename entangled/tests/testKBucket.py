#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

import unittest

import kademlia.kbucket
import kademlia.contact as contact
import kademlia.constants

class KBucketTest(unittest.TestCase):
    """ Test case for the KBucket class """
    def setUp(self):
        self.kbucket = kademlia.kbucket.KBucket()

    def testAddContact(self):
        # test if contacts can be added to empty list
        # add k contacts to bucket
        for i in range(kademlia.constants.k):
            tmpContact = contact.Contact('tempContactID%d' % i, str(i), i, i)
            result = self.kbucket.addContact(tmpContact)
            self.failIf(self.kbucket._contacts[i] != tmpContact, "Contact in position %d not then same as the newly added contact" % i)

        # test if contact is not added to full list
        i += 1
        tmpContact = contact.Contact('tempContactID%d' % i, str(i), i, i)
        self.failUnlessRaises(kademlia.kbucket.BucketFull, self.kbucket.addContact, tmpContact)

    def testGetContacts(self):
        # try and get 2 contacts from empty list
        result = self.kbucket.getContacts(2)
        self.failIf(len(result) != 0, "Returned list should be empty; returned list length: %d" % (len(result)))

        # Add k-2 contacts
        for i in range(kademlia.constants.k-2):
            tmpContact = contact.Contact(i,i,i,i)
            self.kbucket.addContact(tmpContact)

        # try to get too many contacts
        # requested count greater than bucket size
        self.failUnlessRaises(IndexError, self.kbucket.getContacts, kademlia.constants.k+3)

        # verify returned contacts in list
        for i in range(kademlia.constants.k-2):
            self.failIf(self.kbucket._contacts[i].id != i, "Contact in position %s not same as added contact" % (str(i)))
        
        # try to get too many contacts
        # requested count one greater than number of contacts
        result = self.kbucket.getContacts(kademlia.constants.k-1)
        self.failIf(len(result) != kademlia.constants.k-2, "Too many contacts in returned list %s - should be %s" % (len(result), kademlia.constants.k-2))

        # try to get contacts
        # requested count less than contact number
        result = self.kbucket.getContacts(kademlia.constants.k-3)
        self.failIf(len(result) != kademlia.constants.k-3, "Too many contacts in returned list %s - should be %s" % (len(result), kademlia.constants.k-3))


    def testRemoveContact(self):
        # clean contact bucket
        #self.kbucket._contacts = list()

        # try remove contact from empty list
        rmContact = contact.Contact('TestContactID1','127.0.0.1',1, 1)
        self.failUnlessRaises(ValueError, self.kbucket.removeContact, rmContact)
        
        # Add couple contacts
        for i in range(kademlia.constants.k-2):
            tmpContact = contact.Contact('tmpTestContactID%d' % i, str(i), i, i)
            self.kbucket.addContact(tmpContact)

        # try remove contact from empty list
        self.kbucket.addContact(rmContact)
        result = self.kbucket.removeContact(rmContact)
        self.failIf(rmContact in self.kbucket._contacts, "Could not remove contact from bucket")


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(KBucketTest))
    return suite

if __name__ == '__main__':
    # If this module is executed from the commandline, run all its tests
    unittest.TextTestRunner().run(suite())
