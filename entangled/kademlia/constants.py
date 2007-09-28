#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

""" This module defines the charaterizing constants of the Kademlia network """

# Small number Representing the degree of parallelism in network calls
alpha = 3

# Maximum number of contacts stored in a bucket; this should be an even number
k = 8

# Timeout for network operations (in seconds)
rpcTimeout = 20

# Delay between iterations of iterative node lookups (for loose parallelism)  (in seconds)
iterativeLookupDelay = rpcTimeout * 2/3
