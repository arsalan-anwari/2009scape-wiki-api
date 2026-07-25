SELECT
    COUNT(*) AS total
FROM edge
WHERE src_type = :type
  AND src_id = :id
  AND (:rel IS NULL OR rel = :rel);
