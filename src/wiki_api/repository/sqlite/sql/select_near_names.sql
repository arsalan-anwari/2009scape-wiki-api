SELECT
    e.id,
    e.name
FROM entity AS e
WHERE e.type = :type
  AND e.searchable = 1
ORDER BY e.id;
