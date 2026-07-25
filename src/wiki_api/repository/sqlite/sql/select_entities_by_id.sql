SELECT
    e.*
FROM entity AS e
WHERE e.type = :type
  AND e.visibility = :visibility
  AND e.canonical_id IS NULL
ORDER BY e.id
LIMIT :limit
OFFSET :offset;
