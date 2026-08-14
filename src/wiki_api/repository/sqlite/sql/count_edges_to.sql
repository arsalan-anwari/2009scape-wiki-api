SELECT
    COUNT(*) AS total
FROM edge AS e
JOIN json_each(:keys) AS requested
  ON e.dst_type = json_extract(requested.value, '$.type')
 AND e.dst_id = json_extract(requested.value, '$.id')
WHERE (:rel IS NULL OR e.rel = :rel)
  AND (:sorts IS NULL OR e.src_type IN (SELECT value FROM json_each(:sorts)))
  AND (:include_hidden OR NOT EXISTS (
        SELECT 1
        FROM entity AS target
        WHERE target.type = e.src_type
          AND target.id = e.src_id
          AND target.visibility = :hidden
      ));
