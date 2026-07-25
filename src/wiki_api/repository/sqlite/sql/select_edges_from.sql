SELECT
    *
FROM edge
WHERE src_type = :type
  AND src_id = :id
  AND (:rel IS NULL OR rel = :rel)
ORDER BY rel, order_key, dst_type, dst_id, discriminator;
