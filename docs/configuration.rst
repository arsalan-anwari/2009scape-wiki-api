Configuration
=============

Every setting is a field of ``wiki_api.config.Settings`` and a ``WIKI_API_`` prefixed
environment variable (Example: ``http_port`` is ``WIKI_API_HTTP_PORT``). 

Read from four places, first ``Settings`` arguments, then local environment ``.env``
finally config file ``deploy.json``. 

``deploy.json`` sits beside the keys, or wherever ``WIKI_API_CONFIG_FILE`` names. Copy
``deploy.example.json`` for a complete one. Each install puts both somewhere already:

=====================  ==========================================  ==========================================
installed as           ``deploy.json``                             ``data_dir``
=====================  ==========================================  ==========================================
PyPI                   ``~/.config/scape2009-wiki-api/``           ``~/.local/share/scape2009-wiki-api``
a container            ``/config/`` (mount it)                     ``/data`` (in the image)
a system package       ``/etc/scape2009-wiki-api/``                ``/usr/share/scape2009-wiki-api``
a checkout             ``~/.config/scape2009-wiki-api/``           ``data/``
=====================  ==========================================  ==========================================

Data
----

=========================  ===========================================  ==============================================
setting                    default                                      what it does
=========================  ===========================================  ==============================================
``data_dir``               ``~/.local/share/scape2009-wiki-api``        Where the artifact and staged sources live.
``artifact_filename``      ``knowledge.sqlite3``                        The file a surface opens.
``staged_dirname``         ``source``                                   The staged sources, under ``data_dir``.
``hf_repo_id``             ``arsalan-anwari/2009scape-wiki-api-data``   Which published dataset ``data pull`` fetches.
``hf_revision``            ``main``                                     Which build of it. A commit pins an older one.
``game_data_dir``          ``game_data``                                The game repositories, build time only.
``overlay_dir``            ``overlays``                                 Hand corrections, build time only.
``identity_dir``           ``identity``                                 Allocated ids, build time only.
=========================  ===========================================  ==============================================

Surfaces
--------

=========================  =================  =============================================
setting                    default            what it does
=========================  =================  =============================================
``surfaces``               ``both``           One of ``http``, ``mcp``, ``both``.
``http_host``              ``127.0.0.1``      Set to ``0.0.0.0`` inside a container.
``http_port``              ``8000``
``mcp_transport``          ``stdio``          ``http`` when no client spawns the process.
``mcp_host``               ``127.0.0.1``      Read only when the transport is ``http``.
``mcp_port``               ``8009``           Read only when the transport is ``http``.
``cors_origins``           none               Origins the browser contract answers.
=========================  =================  =============================================

The tools over stdio install no guard, and are the only case that starts without a key.
See :doc:`access`.

Answer sizes
------------

=========================  ===========  ===================================================
setting                    default      what it does
=========================  ===========  ===================================================
``block_rows``             ``60``       Rows in one relationship block of an HTTP page.
``mcp_rows``               ``10``       Rows in one MCP answer.
``near_limit``             ``5``        Near names offered for a name that matched nothing.
``near_keep``              ``0.9``      How close to the best match a candidate must be.
``near_floor``             ``0.6``      How close a candidate must be at all.
``cache_seconds``          ``300``      ``max-age`` on a page.
``tooltip_cache_seconds``  ``3600``     ``max-age`` on a tooltip.
=========================  ===========  ===================================================

The guard
---------

==========================  =================  ================================================
setting                     default            what it does
==========================  =================  ================================================
``auth_mode``               ``required``       ``off`` answers everyone.
``auth_public_key``         none               The issuer public key inline.
``auth_public_key_file``    beside the keys    Where to read the issuer public key from.
``auth_revoked_file``       beside the keys    The withdrawn key ids.
``ban_file``                beside the keys    Where shut-out addresses are written.
``rate_per_second``         ``10.0``           One caller's steady share.
``rate_burst``              ``60``             How far a caller may run ahead of it.
``max_refusals``            ``10``             Refusals in the window before a shut-out.
``refusal_window``          ``60.0``           The window, in seconds.
``ban_seconds``             ``900.0``          The first ban. Repeats grow it.
``guard_entries``           ``10000``          How many callers are tracked at once.
``trusted_proxies``         none               Whose forwarded-for header is believed.
==========================  =================  ================================================

See :doc:`access` for what these mean in practice, and :doc:`architecture` for why a
process serving both runs a single worker.
