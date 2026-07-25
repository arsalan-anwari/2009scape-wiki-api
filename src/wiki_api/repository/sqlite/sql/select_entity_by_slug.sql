SELECT
    e.type,
    e.id
FROM entity AS e
WHERE e.type = :type
  AND e.slug = :slug;
