# Background Story
This project started as a forum for a diverse bunch of experience colleagues to learn `Python`.  Very soon we decided that we need a more challenging and real project to implement.  We wanted to learn network and threading programming.  We search for sample code and ended up with some mutli-casting chat server example as our starting point.  We also talked about all the external services used in some application architecture and wonder if they could be removed to reduce complexity and cost.

Finally, we decided on implementing a distributed cache that do **not** introduce any new ways but keep the same `Python` dictionary usage experience.

First we kept it simple to fit our understanding and to deliver working code.  We limit the size of the cached object small.  Each member maintain their owe cache and do not share it.  Any updates to each local cache will be broadcast out an eviction so that the next lookup shall be reprocessed thus be the freshest.  If there is no changes to the underneath platform, they should have the same processed result.

Very soon, we realized that it is a fun academic learning but not functional enough to use it in our own project.  `McCache` functional requirements are:
* Reliable
* Performant

Other non-functional technical requirements are:
* Handle large message
* Small code base
* Not "complex" beyond our skill set and understanding

Building a simple distributed system is more challenging than we originally thought.  You may question some design decision but we arrive here from a collection of wrong and right turns on a long learning journey but we agreed to delivering a good enough working software is the most important compromise.  In the future if we still feel strongly for a re-factoring or a re-design, this option is always available to us.  We are still on this journey of learning and hopefully contribute something of value back into the community.  (circa Oct-2023)

It too so long because there was slew of very subtle bugs in both the cache implementation and also in the stress test script.  We were also getting **false negative** results that send down the wrong path hunting for bugs.  Narrowing the bug down was very discouraging and we took some time off.
