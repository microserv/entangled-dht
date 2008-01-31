# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive

""" Entangled DHT and distributed tuple space

The distributed hash table (DHT) used by Entangled is based on Kademlia,
and be accessed by the "entangled.kademlia package", or by simply
instantiating/subclassing the exposed KademliaNode in the main "entangled"
package.

On top of this Kademlia node Entangled provides some extra functionality
in the form of a "DELETE" RPC and keyword-based search operations; these
functions are accessible via the EntangledNode class in the main "entangled"
package.

The Entangled distributed tuple space is exposed as the
DistributedTupleSpacePeer class, accessible via the main "entangled" package
or its "dtuple" module.
"""

from kademlia.node import Node as KademliaNode
from node import EntangledNode
from dtuple import DistributedTupleSpacePeer
