Keys and access
===============

A deployment answers key holders and nobody else. Only the public half of a key need
ever reach a running process, so a server can check tokens without being able to mint
one.

Commands
--------

Six of them, and they take the same arguments however this was installed. What differs
is how you invoke them, so take your own line below and put it in front of each.

uv tool
~~~~~~~

.. code-block:: bash

   scape2009-wiki-keys init                     # the key this deployment answers, once
   scape2009-wiki-keys issue --label <label>   # one token, kept in tokens/<label>.json
   scape2009-wiki-keys revoke --kid <key id>    # stop answering that one
   scape2009-wiki-keys show                     # the public key, and what is withdrawn
   scape2009-wiki-keys banned                   # which addresses are being refused
   scape2009-wiki-keys unban --caller 1.2.3.4   # answer one of them again

System package
~~~~~~~~~~~~~~

As root, because the keys belong to ``/etc`` rather than to you.

.. code-block:: bash

   sudo scape2009-wiki-keys init
   sudo scape2009-wiki-keys issue --label <label>
   sudo scape2009-wiki-keys revoke --kid <key id>
   sudo scape2009-wiki-keys show
   sudo scape2009-wiki-keys banned
   sudo scape2009-wiki-keys unban --caller 1.2.3.4

Container
~~~~~~~~~

Needs a volume for ``/config`` so the keys survive a restart. 
See :doc:`deployment` for how to make one.

.. code-block:: bash

   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api \
     keys init
   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api \
     keys issue --label <label>
   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api \
     keys revoke --kid <key id>
   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api \
     keys show
   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api \
     keys banned
   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api \
     keys unban --caller 1.2.3.4

Checkout
~~~~~~~~

.. code-block:: bash

   uv run poe keys init
   uv run poe keys issue --label <label>
   uv run poe keys revoke --kid <key id>
   uv run poe keys show
   uv run poe keys banned
   uv run poe keys unban --caller 1.2.3.4

Files
-----

All of them sit together in the config directory, which is:

==================  ====================================
installed as        config directory
==================  ====================================
uv tool             ``~/.config/scape2009-wiki-api``
system package      ``/etc/scape2009-wiki-api``
container           ``/config``, the volume you mount
checkout            ``~/.config/scape2009-wiki-api``
==================  ====================================

=========================  ==============  ==============================================
file                       belongs to      what it is
=========================  ==============  ==============================================
``issuer.key``             you             signs tokens; no server ever needs it
``issuer.pub``             the service     checks them; all a server needs
``revoked.json``           the service     the key ids no longer answered
``banned.json``            the service     shut-out addresses, and must be writable
``tokens/<label>.json``    the caller      one issued token, for whoever asked for it
``deploy.json``            the service     the settings this deployment reads
=========================  ==============  ==============================================

``WIKI_API_CONFIG_DIR`` or ``XDG_CONFIG_HOME`` moves the lot. With nowhere writable to
put them, pass ``WIKI_API_AUTH_PUBLIC_KEY`` inline instead.

Before relying on it
--------------------

- Tokens are Ed25519 signatures and never expire. A leaked one is answered until it is
  revoked by key id, or until the issuer key is replaced, which refuses every token.
- Repeated refusals shut an address out for longer each time, written to
  ``banned.json`` so a restart does not forget it.
- A real key asking too fast gets a ``Retry-After`` rather than a ban.
- A caller's share is counted per process. Two replicas mean two shares.
- ``/health`` is the only path answered without a token.
- Every refusal reads the same to the caller, whatever the real reason was.

Over stdio, no key
------------------

The tools over stdio are spawned by the client reading them, so there is no caller to
tell apart, no guard is installed, and no key is asked for at startup.

``WIKI_API_AUTH_MODE=off`` answers everyone: right for a local front end, wrong for
anything reachable from off the machine.
