SELECT
    e.*
FROM entity AS e
JOIN json_each(:keys) AS requested
  ON e.type = json_extract(requested.value, '$.type')
 AND e.id = json_extract(requested.value, '$.id')
ORDER BY e.type, e.id;
