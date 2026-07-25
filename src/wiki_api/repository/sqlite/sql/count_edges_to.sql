SELECT
    COUNT(*) AS total
FROM edge
WHERE dst_type = :type
  AND dst_id = :id
  AND (:rel IS NULL OR rel = :rel);
