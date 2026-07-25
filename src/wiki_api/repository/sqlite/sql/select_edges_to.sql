SELECT
    *
FROM edge
WHERE dst_type = :type
  AND dst_id = :id
  AND (:rel IS NULL OR rel = :rel)
ORDER BY rel, order_key, src_type, src_id, discriminator;
