SELECT
    e.*
FROM entity AS e
WHERE e.type = :type
  AND e.id = :id;
