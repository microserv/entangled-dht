#!/usr/bin/env python
#
# This file is part of Entangled, and is free software, distributed under the
# terms of the GNU Lesser General Public License Version 3, or any later
# version.
# See the COPYING file included in this archive

import sys

if sys.version_info < (2,5):
    print >>sys.stderr, "Entangled requires at least Python 2.5"
    sys.exit(3)
else:
    try:
        # Since Twisted does not provide egg-info by default, check if we can
        # import it instead of using install_requires in setup()
        import twisted
    except ImportError:
        print >>sys.stderr, "Entangled requires Twisted (Core) to be installed"

from setuptools import setup, find_packages

setup(
      name='entangled',
      version='0.1',
      url='http://entangled.sourceforge.net',
      # Temporary download URL enabling SVN checkouts (until first file release)
      download_url='https://entangled.svn.sourceforge.net/svnroot/entangled#egg=entangled-0.1',
      
      packages=find_packages(),
      test_suite='tests/runalltests',

      author='Francois Aucamp',
      author_email='faucamp@csir.co.za',
      description='DHT based on Kademlia, and p2p tuple space implementation',
      license='LGPLv3+',
      keywords="dht distributed hash table kademlia peer p2p tuple space twisted",
      
      long_description='Entangled is a distributed hash table (DHT) based on '
                       'Kademlia, as well as a distributed, peer-to-peer '
                       'tuple space implementation. This can be used as a '
                       'base for creating peer-to-peer (P2P) network '
                       'applications that require synchronization and event '
                       'handling (such as distributed resource provisioning '
                       'systems) as well as applications that do not (such as '
                       'file sharing applications).',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Communications :: File Sharing',
          'Topic :: Internet',
          'Topic :: Software Development :: Libraries',
          'Topic :: System :: Networking',
          ],
)
