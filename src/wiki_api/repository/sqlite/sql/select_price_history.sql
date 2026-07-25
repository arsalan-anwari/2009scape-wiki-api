SELECT
    item_id,
    snapshot_date,
    value
FROM price_history
WHERE item_id = :item_id
  AND (:since IS NULL OR snapshot_date >= :since)
ORDER BY snapshot_date;
