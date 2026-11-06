-- 0007_entry_metadata — what an entry is about, in words a visitor can read
--
-- A model drafts a title, the question that was asked and a few keywords from the
-- *approved* Arabic; a person corrects and confirms them. Keywords are free text on
-- purpose: every topic is accepted, so no fixed list limits what an entry may be about.
-- `topic_id` stays for the browse tree and the `excluded` gate, and is not set here.
--
-- `metadata_state` says who stands behind the words: 'none' (nothing yet), 'draft' (a
-- model wrote it, nobody has read it), 'confirmed' (a person saved it).

ALTER TABLE entry
    ADD COLUMN question_en    text,
    ADD COLUMN keywords       text[] NOT NULL DEFAULT '{}',
    ADD COLUMN metadata_state text   NOT NULL DEFAULT 'none'
        CONSTRAINT entry_metadata_state_known CHECK (metadata_state IN ('none', 'draft', 'confirmed'));
