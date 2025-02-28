#  pipenv   sync
#  pipenv   install mccache
#  pipenv   run     python

import  os
import  time
from    pprint  import  pprint    as  pp


# Get a demo cache.
import  mccache
c = mccache.get_cache( 'demo' )
pp( dict(c) )


# Insert a cache entry
k = os.environ.get( 'KEY1' ,'k1' )
c[ k ] = time.ctime( time.time() )
print(f"Inserted on {c[ k ]}")
pp( dict(c) ,indent=2 ,width=40)


# Update a cache entry
c[ k ] = time.ctime( time.time() )
print(f"Updated  on {c[ k ]}")
print(f"Metadata for key '{k}' is {c.metadata[ k ]}")
pp( dict(c) ,indent=2 ,width=40)


# Insert 2nd cache entry
k = os.environ.get( 'KEY2' ,'k2' )
c[ k ] = time.ctime( time.time() )
print(f"Inserted on {c[ k ]}")
pp( dict(c) ,indent=2 ,width=40)


# Insert 3rd cache entry
k = os.environ.get( 'KEY3' ,'k3' )
c[ k ] = time.ctime( time.time() )
print(f"Inserted on {c[ k ]}")
pp( dict(c) ,indent=2 ,width=40)


#
pp( mccache.get_local_metrics( 'demo' ))
