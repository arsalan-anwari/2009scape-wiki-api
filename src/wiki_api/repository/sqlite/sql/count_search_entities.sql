SELECT
    COUNT(*) AS total
FROM entity_fts
JOIN entity AS e
  ON e.search_id = entity_fts.rowid
WHERE entity_fts MATCH :match
  AND e.type IN (SELECT value FROM json_each(:types));
