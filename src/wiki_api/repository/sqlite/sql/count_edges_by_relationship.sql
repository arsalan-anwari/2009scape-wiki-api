SELECT
    e.rel AS rel,
    COUNT(*) AS total
FROM edge AS e
GROUP BY e.rel;
