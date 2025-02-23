# Background Story
This project started as a forum for a diverse bunch of experience colleagues to learn `Python`.  Very soon we decided that we need a more challenging and real project to implement.  We wanted to learn network and threading programming.  We search for sample code and ended up with some multi-casting chat server example as our starting point.  We also talked about all the external services used in some application architecture and wonder if they could be removed to reduce complexity and cost.

Finally, we decided on implementing a distributed cache that do **not** introduce any new ways but keep the same `Python` dictionary usage experience.  We started with `cachetool` but we ended up making a lot of  enhancements to it that we decided to write our own cache called `PyCache` that subclass from the `OrderedDict`.

First we kept it simple to fit our understanding and to deliver working code.  We limit the size of the cached object small.  Each member maintain their owe cache and do not share it.  Any updates to each local cache will be broadcast out an eviction so that the next lookup shall be reprocessed thus be the freshest.  If there is no changes to the underneath platform, they should have the same processed result.

Very soon, we realized that it is a fun academic learning but not functional enough to use it in our own project.  `McCache` functional requirements are:
* Performant
* Reliable
* Secure

Other non-functional technical requirements are:
* Handle large message
* Small code base
* Not "complex" beyond our skill set and understanding

Building a simple distributed system is more challenging than we originally thought.  You may question some design decision but we arrive here from a collection of wrong and right turns on a long learning journey but we agreed to delivering a good enough working software is the most important compromise.  In the future if we still feel strongly for a re-factoring or a re-design, this option is always available to us.  We are still on this journey of learning and hopefully contribute something of value back into the community.  (circa Oct-2023)

It took so long because there was slew of very subtle bugs in both the cache implementation and also in the stress test script.  We were also getting **false negative** results that send down the wrong path hunting for bugs.  Narrowing the bug down was very discouraging and we took some time off.  Some of the bugs are:
* Ping-Pong messages between the nodes.
* Memory leak.
* Race condition.

It is a very satisfying project for we came up with our original design and implementation before we found suggestions through Google search.  We **do not** know what we **do not** know until much later.  It was very  emotional too especially when we ran into a wall and nothing works.  It is good to step back and take break and then return back working on the project.

Peeking into the future, we may consider expanding the family by porting `McCache` to other languages.  If we ever decide to, we **do not** want to re-write the core `McCache` for every language we are interested in.  Therefore, we have to consider building the core `McCache` with a memory safe system language and provide the bindings to the other languages.  Furthermore, having the core written is a system language should also give us some performance gain.  The following are some candidate system language to consider:
* [C/C++](https://www.boost.org/) - The Boost library is great.  The old faithful.
* [Rust](https://www.rust-lang.org/) - Trending upwards in the Python world.  The current champ.
* [V](https://vlang.io/) - Nice readable syntax with co-routines that compile fast.  The new contender.

[Swig](https://www.swig.org/) is a candidate tool to generate the bindings for the popular languages such as:
* C#
* Java
* Python
* Ruby

SEE: [Hash Benchmark](https://github.com/andremedeiros/hash_benchmark) as the starting point to select a good hash table implementation.
