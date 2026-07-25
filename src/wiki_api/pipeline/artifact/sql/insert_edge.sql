INSERT INTO edge (
    src_type,
    src_id,
    rel,
    dst_type,
    dst_id,
    discriminator,
    attributes,
    order_key,
    source,
    source_ref,
    game_version
) VALUES (
    :src_type,
    :src_id,
    :rel,
    :dst_type,
    :dst_id,
    :discriminator,
    :attributes,
    :order_key,
    :source,
    :source_ref,
    :game_version
);
