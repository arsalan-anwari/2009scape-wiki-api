SELECT
    e.*,
    -bm25(entity_fts, 10.0, 5.0, 1.0) AS score
FROM entity_fts
JOIN entity AS e
  ON e.search_id = entity_fts.rowid
WHERE entity_fts MATCH :match
  AND e.type IN (SELECT value FROM json_each(:types))
ORDER BY score DESC, e.name, e.id
LIMIT :limit
OFFSET :offset;
