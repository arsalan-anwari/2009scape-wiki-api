SELECT
    a.entity_id,
    a.kind
FROM entity_alias AS a
WHERE a.type = :type
  AND a.alias_slug = :slug;
