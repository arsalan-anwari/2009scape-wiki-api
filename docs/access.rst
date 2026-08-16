Keys and access
===============

A deployment answers key holders and nobody else. Keys are made on your own machine and
only the public half reaches a running process, so nothing in a container can mint a
token. An import contract enforces that rather than convention.

Commands
--------

.. code-block:: bash

   uv run poe keys init                     # the key this deployment answers, once
   uv run poe keys issue --label the-wiki   # one token, kept in tokens/the-wiki.json
   uv run poe keys revoke --kid <key id>    # stop answering that one
   uv run poe keys show                     # the public key, and what is withdrawn
   uv run poe keys banned                   # which addresses are being refused
   uv run poe keys unban --caller 1.2.3.4   # answer one of them again

On an installed system these are ``scape2009-wiki-keys init`` and so on.

Files
-----

Everything lives in ``~/.config/scape2009-wiki-api`` unless ``WIKI_API_CONFIG_DIR`` or
``XDG_CONFIG_HOME`` says otherwise. Where there is no writable config directory, pass
``WIKI_API_AUTH_PUBLIC_KEY`` inline and nothing more.

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
- Keys are only checked over HTTP, never over stdio.
- Every refusal reads the same to the caller, whatever the real reason was.

``WIKI_API_AUTH_MODE=off`` answers everyone. That is right for a local front end and
wrong for anything reachable from outside the machine.
