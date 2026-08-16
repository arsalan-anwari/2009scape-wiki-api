Keys and access
===============

A deployment answers key holders and nobody else. Keys are made on your machine; only
the public half reaches a running process, so nothing in a container can mint a token.


Commands
--------

.. code-block:: bash

   scape2009-wiki-keys init                     # the key this deployment answers, once
   scape2009-wiki-keys issue --label the-wiki   # one token, kept in tokens/the-wiki.json
   scape2009-wiki-keys revoke --kid <key id>    # stop answering that one
   scape2009-wiki-keys show                     # the public key, and what is withdrawn
   scape2009-wiki-keys banned                   # which addresses are being refused
   scape2009-wiki-keys unban --caller 1.2.3.4   # answer one of them again

In a container that is ``docker run --rm -v ./config:/config <image> keys init``, and
in a checkout ``uv run poe keys init``.

Files
-----

In ``~/.config/scape2009-wiki-api`` unless ``WIKI_API_CONFIG_DIR`` or
``XDG_CONFIG_HOME`` says otherwise. With no writable config directory, pass
``WIKI_API_AUTH_PUBLIC_KEY`` inline instead.

=========================  ==============  ===========================================
file                       belongs to      goes
=========================  ==============  ===========================================
``issuer.key``             you             nowhere else, ever
``issuer.pub``             the service     ``/config``, all a container needs
``revoked.json``           the service     beside the public key
``banned.json``            the service     beside the public key, and must be writable
``tokens/<label>.json``    the caller      the caller, never the container
``deploy.json``            the service     ``/config``
=========================  ==============  ===========================================

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
