SELECT
    COUNT(*) AS total
FROM edge AS e
JOIN json_each(:keys) AS requested
  ON e.src_type = json_extract(requested.value, '$.type')
 AND e.src_id = json_extract(requested.value, '$.id')
WHERE (:rel IS NULL OR e.rel = :rel)
  AND (:sorts IS NULL OR e.dst_type IN (SELECT value FROM json_each(:sorts)))
  AND (:include_hidden OR NOT EXISTS (
        SELECT 1
        FROM entity AS target
        WHERE target.type = e.dst_type
          AND target.id = e.dst_id
          AND target.visibility = :hidden
      ));
