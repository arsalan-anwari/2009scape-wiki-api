SELECT
    COUNT(*) AS total
FROM entity AS e
WHERE e.type = :type
  AND e.visibility = :visibility
  AND e.canonical_id IS NULL
  AND (:named IS NULL OR e.name = :named)
  AND (:order_path IS NULL OR json_extract(e.attributes, :order_path) IS NOT NULL)
  AND NOT EXISTS (
      SELECT 1
      FROM json_each(:conditions) AS asked
      WHERE NOT (
          json_extract(e.attributes, json_extract(asked.value, '$.path')) IS NOT NULL
          AND (
              (json_extract(asked.value, '$.compare') = 'at_least'
               AND json_extract(e.attributes, json_extract(asked.value, '$.path'))
                   >= json_extract(asked.value, '$.value'))
           OR (json_extract(asked.value, '$.compare') = 'more_than'
               AND json_extract(e.attributes, json_extract(asked.value, '$.path'))
                   > json_extract(asked.value, '$.value'))
           OR (json_extract(asked.value, '$.compare') = 'at_most'
               AND json_extract(e.attributes, json_extract(asked.value, '$.path'))
                   <= json_extract(asked.value, '$.value'))
           OR (json_extract(asked.value, '$.compare') = 'less_than'
               AND json_extract(e.attributes, json_extract(asked.value, '$.path'))
                   < json_extract(asked.value, '$.value'))
           OR (json_extract(asked.value, '$.compare') = 'equals'
               AND json_extract(e.attributes, json_extract(asked.value, '$.path'))
                   = json_extract(asked.value, '$.value'))
          )
      )
  );
