SELECT
    e.*
FROM entity AS e
WHERE e.type = :type
  AND e.canonical_id = :id
ORDER BY e.id;
