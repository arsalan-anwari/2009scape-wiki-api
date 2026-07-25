SELECT
    COUNT(*) AS total
FROM entity AS e
WHERE e.type = :type
  AND e.visibility = :visibility
  AND e.canonical_id IS NULL;
