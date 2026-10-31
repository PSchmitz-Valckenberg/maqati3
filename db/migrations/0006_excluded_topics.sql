-- 0006_excluded_topics — the inherited topic lock, written down once
--
-- CLAUDE.md, "What `excluded` means". An excluded topic is not merely kept out of the
-- search index: it is gone from the public site — no node in the browse tree, no entry
-- page, no transcript, nothing citable. The harm channel is the deep link, and a browse
-- tree is an invitation.
--
-- The lock is inherited. A sub-topic of an excluded topic is excluded, however deep,
-- and so is any entry filed under either, whatever the entry's own fields say.
-- `0001_init.sql` wrote the rule as `COALESCE(t.content_class, 'open') <> 'excluded'`
-- over the entry's own topic, which is the right answer for a top-level topic and the
-- wrong one for every sub-topic beneath it.
--
-- Inheritance is a recursive question, so it is asked in exactly one place: this view.
-- The library repository and `segment_citable` both read it rather than restating it.

CREATE RECURSIVE VIEW topic_excluded(id) AS
        SELECT id FROM topic WHERE content_class = 'excluded'
    UNION
        SELECT child.id
          FROM topic child
          JOIN topic_excluded parent ON child.parent_id = parent.id;

-- UNION, not UNION ALL, on purpose: `topic.parent_id` is an unconstrained self-reference,
-- so a chain that loops back on itself is possible. UNION discards the rows it has already
-- seen and the recursion terminates; UNION ALL would run until the server ran out of
-- memory, and it would do so inside the gate that keeps this material off the site.

COMMENT ON VIEW topic_excluded IS
    'Every topic that is excluded, by its own content_class or by inheriting one.';

-- Same columns, same order as 0001, so the view is replaced in place rather than dropped
-- and rebuilt: only the last condition changes, from the entry's own topic to the
-- inherited answer.
CREATE OR REPLACE VIEW segment_citable AS
SELECT s.id         AS segment_id,
       s.entry_id,
       s.idx,
       s.t_start_ms,
       s.t_end_ms,
       e.scholar_id,
       e.topic_id,
       e.attribution,
       st.lang,
       st.text_raw,
       st.text_norm
FROM segment s
JOIN entry e        ON e.id = s.entry_id
JOIN segment_text st ON st.segment_id = s.id
JOIN entry_language el ON el.entry_id = e.id AND el.lang = st.lang
WHERE e.visibility   = 'public'
  AND e.attribution <> 'not_sure'
  AND e.canonical_id IS NULL          -- variants are never indexed, only linked
  AND s.citable
  AND s.span_role    = 'scholar_own'  -- never quote the questioner or a refuted view
  AND el.state       = 'approved'
  AND NOT EXISTS (SELECT 1 FROM topic_excluded x WHERE x.id = e.topic_id);
