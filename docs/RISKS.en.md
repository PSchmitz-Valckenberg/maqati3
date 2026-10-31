# Risks

*From the adversarial critic agent.*

## Kill shots — how the project could realistically fail

- The translation and review workload is one to two orders of magnitude larger than the volunteer team. Realistically, 1,000 hours of audio require 20,000–25,000 person-hours (correction at 20–40% WER, plus MT post-editing in two target languages, plus review). With 20 volunteers working 4 hours per week, that is 5–6 years for one fifth of the target corpus. The technology is not what fails; the volume assumption does. Anyone planning for 50,000 videos is planning for 160,000–200,000 person-hours.

- A single publicly exposed attribution error could destroy the platform permanently. Trust in this field is binary: one misattributed recording, one nuance reversed in a talaq or takfir question, one screenshot in a large group—and the platform becomes the site that put words in Ibn Baz’s mouth. Technically fixable, socially not. The risk increases linearly with corpus size and decreases with review density—exactly the resource you lack.

- Bus factor of 1 across six required specialties (Arabic ASR, forced alignment, cross-lingual RAG, an RTL frontend with six-figure page counts, Linux operations, German media and data-protection law), plus community management. The project does not die from one bug, but from one person’s exhaustion—and afterward nobody can even keep the system running.

- Governance vacuum: without a named, accountable brother with Islamic knowledge (*ilm*), the product is irresponsible; with him, he becomes a bottleneck and the party liable. Even the list of included scholars is a *manhaj*-political position in an ongoing schism—it can split the team before any code exists and determines whose material you receive and whose opposition you face.

- The AI layer is exactly the part the conservative target audience rejects (IslamQA has issued a fatwa against AI fatwas; Dar al-Ifta has issued a prohibition). You could spend nine months building and hear, in response, “We don’t ask a machine,” rather than “This is misquoted.” Then the valuable part—a searchable archive—is ready, and the chatbot is the reason people do not use it.

- Legal and political deplatforming in Germany: a chunk about takfir or *wala wa bara* is presented in isolation in a press article, followed by a chain of actions against the host, payment provider, and domain. In addition, the most likely individual event is an injunction over a translated statement about a living person residing in Germany. Without an association as the legal entity and an export-first operating model, either could threaten the project’s existence.

- The corpus can be accurate while the answers are still wrong, because oral fatwas are situation-specific and your data model does not capture that. No model, reranker, or verifier can solve it—only required fields for the question text, context, date, and degree of generality, set by a human. So this issue, too, depends on the staffing calculations in Kill Shot 1.

---
## Mitigate first

- **Measure throughput instead of estimating it (one afternoon, €0):** Three volunteers each work through 30 minutes of real audio from your target material, timing the entire process—ASR correction, German translation, and review by a second person. Multiply the result by the weekly capacity actually available. This one number determines the target corpus size, and it will probably rule out 50,000 videos. Planning anything else before you have this number is wasted effort.
- **Sample attribution in the raw material (one day, €0):** Have a knowledgeable person check 30 randomly selected clips already circulating on Telegram/YouTube as fatwas by the named scholars against binbaz.org.sa, binothaimeen.net, and alifta.gov.sa. What is the misattribution rate? If it is above 10%, community uploads are dead as a primary source and you must ingest exclusively from official sources—changing the entire ingestion architecture and saving months.
- **Adversarial question set BEFORE building (two days, under $50):** Write 50 questions designed to break the system—negations, “Has Shaykh X ever said…?”, minimal pairs (traveler/resident), comparison questions, takfir, first-person talaq, scholar-versus-scholar, topics with sparse coverage, and time-dependent questions. Then build a throwaway prototype with 50 videos and a frontier model and ask it all 50 questions. Have a brother with *ilm* evaluate it. This tells you in week 1—not month 9—whether the product idea is viable.
- **Translation nuance test (one day, €0):** Run 20 sentences containing *makruh/haram*, *la yanbaghi*, *al-ahwat*, *fihi tafsil*, and conditional constructions through MT and two volunteers. Count how often the legal nuance changes. Above 20% means post-editing alone is not enough; the ruling must be recorded separately as a controlled enum, making the staffing estimate in item 1 even worse.
- **Request for authority and permission (one email):** Send a one-page concept in Arabic to two or three foundations and editorial offices (binothaimeen.net, miraath.net, the al-Fawzan office), asking for permission and feedback on the idea. Their response—or silence—is the most important signal for the whole project: without it, the project is supported neither legally nor religiously, and binothaimeen.net has already set an explicit TDM opt-out in robots.txt. Describe yourselves as an index and search tool for the scholars’ words, never as a mufti.
- **Legal review before writing a single line of production code (90 minutes, €300–500):** Consult a lawyer specializing in IT and media law on three questions—the legal entity and legal notice, liability for translated statements about living people, and Article 9 GDPR for chat without an account. This is the cheapest insurance in the project and prevents the two most likely legal events.
- **Add the cost-cap test and timestamp-integrity test to CI from day 1 (half a day each):** Send 10,000 requests to your own endpoint and verify that the daily hard cap really works before anything is public. In parallel, build the cron job that samples 50 random chunks, rechecks the audio from `start_ms` with ASR, and alerts below 70% agreement—plus a canary row with `state=pending` that checks hourly whether the review filter is still in the retrieval path. These are the only safeguards against the two quietest classes of failure.
- **Put the scope decision in writing (one meeting):** Which scholars, which topics are explicitly excluded (*Jarh wa Ta'dil*, judgments about individuals, talaq, inheritance, takfir, oaths), who the *muraji* is, and what realistic monthly commitment they can make. These three decisions are not bureaucracy—they determine the data schema, intent classifier, and liability situation. Decide them later, and you will build the corpus twice.

---
## Complete risk list

### A synthetic fatwa created by merging two scholars’ positions
**religious/content** · Severity: critical · Likelihood: almost certain without structural safeguards

*Scenario:* Question: Is the duff allowed at a wedding? Retrieval returns 4 chunks from Ibn Baz (permission for women at the *walima*) and 3 from al-Albani (the state of the narrations, with the restriction that no men listen). The model writes: “The scholars permit the duff at weddings, provided no men are present.” Every clause is supported by a chunk, every citation is correctly linked—and yet neither scholar ever gave this fatwa. The condition came from A, the permission from B, and A never attached that condition to this permission. An entailment check will not catch this because every individual sentence is entailed. The user acts on it and attributes it to Ibn Baz.

*Early warning signal:* In a test run of 50 questions, answers contain collective formulations without names: “the scholars,” “there is consensus,” “according to the scholars.” Every occurrence is a hit.

*Mitigation:* Structural controls, not prompt instructions. (1) One evidence block per scholar; chunks from different scholars never go in the same block. (2) An answer schema with no field for a collective opinion—only a list of positions, each with exactly one `scholar_id`, a *dalil* field, and at least one citation. What has no field cannot be written by the model. (3) The verifier checks attribution coverage: if an al-Albani `chunk_id` supports a sentence attributed to Ibn Baz, the answer fails. (4) A regex blocklist for collective formulations as the final safeguard.

### A situation-specific fatwa is presented as a general rule
**religious/content** · Severity: critical · Likelihood: almost certain

*Scenario:* The questioner describes his situation for two minutes: he lives in the West, has no other job, and his family depends on it. The scholar answers for 40 seconds: “In your case, there is no problem with it.” Your chunking cuts at the Q&A boundary, retrieval returns precisely those 40 seconds, and the deep link jumps exactly there. The system outputs: “Shaykh X permits working at a bank,” source: video, minute 14:20. The hardship that conditioned the answer and the follow-up (“but keep looking for another job”) are not in the chunk. This is not a model error but a data-model error—and it affects the majority of audio fatwas, because oral answers are almost always given in response to a specific case.

*Early warning signal:* In a sample of 30 answers, it is impossible to tell from the cited chunk itself whether the statement is general or case-specific for more than a third of the chunks. This can be measured even before you have users.

*Mitigation:* Required schema fields, not prompt instructions: `question_text_ar` (the questioner’s full question), `context_note` (occasion, location, program, year), and `generality` (`general | case_specific | unclear`, set by the reviewer, default `unclear`). Retrieval rule: chunks where `generality != general` may be shown only if the questioner’s text is provided and displayed above the answer in the UI. The deep link always starts 20 seconds BEFORE the chunk, never at its beginning. When `generality = unclear`, do not synthesize—only link to the video.

### A scholar’s change of position (*ruju*) remains invisible
**religious/content** · Severity: critical · Likelihood: high (increases with corpus size)

*Scenario:* Al-Albani revised hadith gradings multiple times (shifts between *Silsila Da'ifa* and *Sahiha*); Ibn Uthaymin recanted on individual issues. The corpus contains a 1988 cassette and a 1997 lecture, both on the same topic. Retrieval selects the older one because it is a better semantic match (more clearly worded, fewer asides). The system cites a position the scholar himself withdrew—with name, date, and deep link, making it maximally credible. No retrieval system can solve this because the fact that a *ruju* occurred is not in the text.

*Early warning signal:* Two chunks by the same scholar on the same topic, more than three years apart, with contradictory rulings. This can be found automatically once `scholar_id`, date, and topic are recorded reliably—and it is exactly the list a reviewer needs to examine.

*Mitigation:* Add `supersedes` / `superseded_by` fields at the chunk level and a `ruju_bekannt` flag. An automatic conflict detector (same scholar, same topic, contradictory ruling terms) sends entries to a review queue. Until reviewed, show BOTH sources side by side with their dates and do not synthesize. Date is therefore a required field, not a nice-to-have: undated audio must not be cited in conflict cases. Realistically, only a person with *ilm* can resolve this—so keep the conflict list short by growing the corpus deeply rather than broadly by topic.

### Misattributed audio in circulation (including AI voice clones)
**religious/content** · Severity: critical · Likelihood: high

*Scenario:* A brother uploads an MP3 in good faith that has circulated in Telegram groups for years as Ibn Baz. In fact, it is a student speaking, or another shaykh with a similar voice on a noisy cassette. It enters a database claiming authority with `scholar_id=ibn-baz`, then gets transcribed, translated, chunked, precomputed, cached—and copied by other sites because you have become the most convenient source. The 2026 variant: someone deliberately generates voice-cloned audio. Hundreds of hours of training material are publicly available, and a platform claiming authority is exactly the kind of target such an attack is worth pursuing. The damage cannot be recalled because it spreads further.

*Early warning signal:* Have a knowledgeable person check 30 circulating clips against binbaz.org.sa / binothaimeen.net / alifta.gov.sa. If the misattribution rate in the raw material is above 10%, community uploads are dead as a primary source.

*Mitigation:* Use provenance classes in the schema instead of trust: `provenance = official_site | verified_broadcast_recording | unverified_community_upload`. Only the first two classes may be cited by the AI tool; `unverified_community_upload` is visible in the library but carries a warning and cannot be cited. `source_url` to an official page is required for the citable class. Also compare transcripts against the existing text corpora on the official sites as automatic attribution evidence—where the text is found there, attribution is confirmed; where it is not, it remains unconfirmed. This is the only scalable attribution test you have.

### Translation changes the legal nuance (*karahah* vs. *tahrim*, condition omitted)
**religious/content** · Severity: critical · Likelihood: almost certain

*Scenario:* The scholar says *la yanbaghi* (“it is not fitting”), *al-ahwat tarkuhu* (“the more cautious course is to leave it”), or *makruh*. The volunteer—or DeepL—writes: “It is forbidden.” Conversely, *la yajuz* becomes “one should preferably avoid it.” Or the most common case: *fihi tafsil* (“the matter requires differentiation”) is omitted because the translator thinks the following subordinate clause is a repetition, turning a conditional permission into an unconditional one. This translation enters the DE index, is retrieved, selected as the best hit by the reranker, and cited by the LLM. The Arabic original is displayed alongside it—but the German user, who uses the platform precisely for this reason, does not read it.

*Early warning signal:* Test 20 sentences containing exactly these patterns with MT and two volunteers. If the nuance changes in more than 20% of cases, post-editing alone is not sufficient.

*Mitigation:* Use a controlled ruling vocabulary instead of free-form translation: the translator translates the text, but the RULING is recorded separately as an enum (`wajib | mustahabb | mubah | makruh | haram | fihi_tafsil | no_ruling`) and displayed in the UI as its own label, not inferred from the prose. Create a glossary with fixed equivalents (300–500 pairs), shown as autocomplete in the review UI, with warnings for deviations. Second safeguard: batch-screening with Haiku compares the Arabic original and German translation in the same call and checks exclusively for ruling strength and omitted conditionals—this costs fractions of a cent per video and catches exactly this class of error.

### Weaponization in internal disputes (*Jarh wa Ta'dil*, scholar against scholar)
**religious/content** · Severity: critical · Likelihood: almost certain

*Scenario:* Someone asks: “What did Shaykh X say about Shaykh Y?” or “Evidence that Z is a *mubtadi*.” In a Salafi corpus, this is not an edge case—there is an entire genre of audio on the subject, and it is among the most searched. Your tool delivers assembled, translated ammunition on demand, sorted by relevance, with deep links. Within weeks, one faction takes over the platform and the others attack it. Contributors split, the claim of neutrality is gone, and material is deliberately submitted to canonize positions. In addition, if Y is a living person residing in Germany, you are distributing a translated defamatory factual allegation as your own content.

*Early warning signal:* The first 200 real queries already include questions of this type. They arise immediately, not later—so they will be visible in the closed beta’s query log before launch.

*Mitigation:* Make the scope decision BEFORE building, not as moderation afterward: evaluations of individuals (*Jarh wa Ta'dil*) must not enter the corpus in the first place—use a dedicated `content_class` field set during ingestion, and exclude this class from the index. Also use an intent classifier on the query (a cheap model, $0.0002) to detect questions asking for judgments about individuals and reject them with a fixed message instead of retrieving results. This will cost you part of the target audience and save the project; the reverse is not true.

### Life-changing individual cases (talaq, inheritance, oaths, takfir) receive generic answers
**religious/content** · Severity: critical · Likelihood: almost certain

*Scenario:* A user types: “I said talaq three times; what applies now?” This is one of the most common reasons people consult fatwa sites at all. Your system retrieves fatwas about triple talaq, finds different positions, summarizes them—and the user acts. But the fatwa depends on the wording, the wife’s state, intent, and the number of previous occasions; without follow-up questions, any answer is wrong. The same structure applies to inheritance shares, oaths, riba contracts, and—most dangerously—takfir questions (“Has my father become a kafir?”). This is also the first type of question a journalist or authority will test.

*Early warning signal:* Query log: first-person questions describing a situation rather than asking a general question. Measure the share in the first few weeks—it will be higher than expected.

*Mitigation:* Use a hard topic blocklist and routing rather than synthesis: talaq, inheritance, oaths/*qasam*, takfir, khul, and medical decisions. For these topics, the system NEVER gives a summarized answer; it only shows sources with a fixed message: “This is an individual case that requires consultation with a scholar or knowledgeable imam.” Detect these through the intent classifier plus a first-person heuristic. This is technically trivial and the single most important safety measure in the entire product.

### Proving absence: has Shaykh X ever said that…?
**retrieval failure** · Severity: high · Likelihood: almost certain

*Scenario:* Question: “Did Ibn Baz ever say demonstrations are permitted?” Your system finds nothing and correctly answers: “There is nothing about this here.” The user reads: “He never said it,” takes a screenshot, and posts it as proof. But your corpus may cover only 2% of the scholar’s entire body of work. The system structurally cannot prove nonexistence, yet the UI suggests completeness because it looks like an archive. The same mechanism affects comparison questions: 8 chunks from A, 0 from B, and the answer implies that B did not comment.

*Early warning signal:* In the adversarial question set, test every question of the form “Has X ever…?”, “Is there a fatwa from X about…?”, or “What is the difference between X and Y?” Check whether the answer makes a claim of absence.

*Mitigation:* Absence is never a statement about the scholar, but about the corpus—and it must be worded exactly that way: “This archive contains no recordings from Shaykh X on this question. The archive currently contains N recordings of him and is incomplete.” Also show a visible coverage indicator on every scholar page (N recordings, M hours, topics covered). Catch “Has X ever said…?” questions with the intent classifier and keep them out of synthesis entirely. For comparison questions, retrieve separately for each named scholar and explicitly report the number of hits per scholar.

### Negation and minimal pairs break retrieval AND caching
**retrieval failure** · Severity: critical · Likelihood: high

*Scenario:* “Is image editing permitted?” and “Is image editing forbidden?” are very close in embedding space—dense models are notoriously weak with negation. Even more dangerous are minimal pairs that reverse the entire case: *musafir* vs. *muqim*, menstruating vs. pure, gold as everyday jewelry vs. investment, with *niyya* vs. without. Two questions with 0.97 cosine similarity have opposite answers. The semantic cache then returns the answer cached for the wrong question—and may do so for months because nothing invalidates it. This is a cached false fatwa with correct citations.

*Early warning signal:* Build 30 minimal pairs (one-line difference, opposite answers) and run them against the cache. Any instance where question A retrieves question B’s cache entry is a production bug.

*Mitigation:* Cache hit only at cosine >= 0.97 AND with a lexical gate: extracted content terms from both questions must reach Jaccard >= 0.8, and a curated list of discriminator tokens (traveler, resident, menstruation, jewelry, investment, intention, not, no, without) must have identical presence; otherwise, cache miss. The cache key must always include `(lang, model_id, corpus_version)`. Have 50 cache hits sampled weekly for review—a false cache hit here is not a poor search result, but a misattributed fatwa.

### Sparse coverage with barely-above-threshold hits—more dangerous than no hits
**retrieval failure** · Severity: high · Likelihood: almost certain

*Scenario:* The problem is not an empty result (abstention handles that), but the zone just above it: two or three weak chunks barely over the threshold. Example: a question about cryptocurrency. The corpus has no fatwa on it, but a lecture from 1994 contains a passing remark about *gharar* in trade. The reranker promotes it because it is the best available. The answer looks more authoritative than any Google search because it includes a citation, name, and timestamp—and it is an extrapolation the scholar never made. This is the most common form of real-world harm, and no verifier catches it because the sentence is supported by the chunk.

*Early warning signal:* Plot the distribution of reranker top-1 scores across real queries. The middle range is dangerous. If more than 20% of queries land there, the threshold is miscalibrated.

*Mitigation:* Use two thresholds instead of one: above the upper threshold, synthesize; between the thresholds, show sources ONLY, without synthesis, and explain that the results only touch on the topic; below the lower threshold, show nothing. Also check topic coverage: if the question’s topic is not among the curated topic tags for which the corpus actually has material, abstain—regardless of score. You need to maintain that topic list for the library anyway.

### Questioner/scholar role confusion—the question is cited as a fatwa
**technical** · Severity: critical · Likelihood: medium to high

*Scenario:* Diarization labels speakers A and B, but the heuristic “longest speaking time = scholar” fails precisely when the questioner speaks at length and in detail—as happens in classic fatwa programs. The question text typically contains a false premise: “Shaykh, some people say X is permitted and cite…”. If that segment is indexed as a scholar segment, your system cites the opposing position as the scholar’s own—in other words, the exact opposite. With the correct timestamp, correct name, and correct deep link.

*Early warning signal:* Sample 50 chunks with `speaker_role=scholar`: if one starts with common questioner phrases (*yaqul as-sa'il*, *fadilat ash-shaikh*, *ahsana Allahu ilayk*, *su'ali huwa*), the role is wrong. This can run as a fully automatic ongoing check.

*Mitigation:* Role is a required field confirmed by review, not the result of a heuristic. Only `speaker_role=scholar` AND `role_confirmed=true` may be cited. Use a phrase detector as an automatic prescreen in both directions (questioner phrases in scholar segments and answer phrases in questioner segments). Index questioner segments separately as question text—they are valuable for retrieval because user questions resemble them—but give them their own type, which is never returned as an answer.

### Timestamp drift—the quietest failure in the entire architecture
**technical** · Severity: critical · Likelihood: high

*Scenario:* Three independent causes: (a) ffmpeg cuts with `-ss` before `-i`, shifting the served file by 0.3 to 2 seconds; (b) a brother omits filler words and merges a repetition while transcribing, causing forced alignment to drift by seconds or minutes from that point onward without reporting an error; (c) `ctc-forced-aligner` receives Arabic script without uroman romanization and returns zero timestamps throughout. In all three cases, everything keeps working: the page loads, the quote is there, and the link is clickable. The user just lands in the middle of an answer to a DIFFERENT question. Nobody notices because nobody clicks all the links, and anyone who does thinks they misheard. This destroys precisely the trust signal on which the entire product idea rests.

*Early warning signal:* A cron job from day 1: sample 50 random chunks, send 10 seconds of audio starting at `start_ms` through ASR again, and fuzzy-match it against the first words of the chunk. Below 70% agreement triggers an alert. Also hard-reject any segment with `t_start==t_end==0` or non-monotonically increasing times.

*Mitigation:* Persist `align_confidence` per segment; below the threshold, DISABLE the deep link rather than jumping to the wrong place (better no jump than a wrong one). Always align against the SERVED file, never the original, and enforce this in an automated test. The ASR run is authoritative for timing, the human text for wording—connect them through text-to-text alignment, not forced alignment against audio.

### `review_state` drops out of the retrieval path—raw machine translation is cited as evidence
**technical** · Severity: critical · Likelihood: medium

*Scenario:* During a hybrid-query refactor, the `state='approved'` filter disappears from the WHERE clause—for example, someone adds an exact-scan path for highly selective filters and forgets the condition there. From that deploy onward, the AI tool cites unreviewed machine output as the scholar’s wording. Nothing breaks, nothing is logged, and the answers even improve (larger pool). It is only noticed when someone outside the project publicly exposes a wrong translation.

*Early warning signal:* Canary row: a dummy chunk deliberately placed in the corpus with `state='pending'` and a unique marker string. A cron job asks the question that would trigger it every hour and alerts if the marker appears in retrieval or in an answer.

*Mitigation:* Canary row plus database-level enforcement instead of application-level enforcement: a `chunks_citable` view that contains the filter, and a database user for the application with no SELECT access to the base table at all. Then the error cannot be forgotten. Also, every served chunk includes its `review_state` in the response payload, and the frontend raises a visible error if it is not approved.

### Translation and correction workload exceeds the volunteer team by one to two orders of magnitude
**organizational** · Severity: critical · Likelihood: almost certain

*Scenario:* Calculation for 1,000 hours of audio (equivalent to about 6,000–7,500 videos of 8–10 minutes). Arabic word count: 1,000 h × 60 × 130 words/min = about 7.8 million words. Transcript correction at a real 20–40% WER on old cassette material: 90–180 minutes per audio hour, or 1,500–3,000 person-hours. Translation: a professional translator handles 2,000–2,500 words per eight-hour day; MT post-editing about 6,000–8,000—so 975 to 3,900 person-days per target language. With MT post-editing and two target languages: about 15,000–20,000 person-hours, plus about 3,000 for review, plus correction. Realistic total: 20,000–25,000 person-hours for 1,000 audio hours. With 20 active volunteers working 4 hours a week, that is 250–310 weeks, or 5–6 years—for one fifth of the target corpus. For the target size of 8,300 audio hours: 160,000–200,000 person-hours. This is not a tight estimate; it is impossible.

*Early warning signal:* Measure in week 1 instead of estimating: three volunteers, 30 minutes of audio each, full process timed. Multiply the resulting hours-per-audio-hour by the total available capacity. Second signal: weekly throughput in weeks 4–6 falls below half of week 1.

*Mitigation:* The target corpus size is the lever, not the technology. Specifically: (1) Limit the target corpus to 300–800 carefully curated fatwas on the 50 most frequently asked *masa'il*—go deep, not broad. A complete, accurate archive on *taharah* and *salah* is more valuable and credible than 50,000 half-reviewed items. (2) Prioritize review based on retrieval hits: review only what actually appears in top-k. (3) Where official text fatwas exist (binbaz.org.sa, alifta), use text-to-audio alignment instead of transcription—this eliminates the largest workload item. (4) The architecture must handle unreviewed material correctly: visibly marked, never quoted verbatim, never used by the AI tool.

### Volunteers drop out after three months—the project is stranded in an unfinished state
**organizational** · Severity: critical · Likelihood: high

*Scenario:* The typical trajectory: initial enthusiasm, a Ramadan peak, then a drop-off. After four months, 3,000 videos have been ingested, 400 reviewed, and 2,600 sit in the system with machine translations. Now only bad options remain: show unreviewed material (attribution risk) or hide it (the platform looks empty despite months of work, and the remaining volunteers cannot see the results of their contributions). Structurally, the project is too large to review and too small to be useful—and it gets stuck in exactly that state.

*Early warning signal:* Weekly active contributor count. If it falls for two weeks in a row, the decline has started. Second signal: the ratio of ingested to reviewed material rises above 3:1.

*Mitigation:* Ingestion throttle: each week, allow no more videos to be ingested than are reviewed that same week (maximum ratio 2:1, enforced as a hard rule in the admin UI). It feels wrong and saves the project. Also use visibility as motivation: a public status page showing every contribution moving from submitted to published, with attribution for those who want it. Small, completed packages (one chapter, ten fatwas) instead of an endless backlog—a completed topic is an achievement; a queue is not.

### Quality varies across contributors—the weakest contributor produces the most
**organizational** · Severity: high · Likelihood: almost certain

*Scenario:* Brother A is a native speaker with *ilm*, takes 3 hours per audio hour, and delivers precise work. Brother B has studied Arabic for two years, pastes DeepL output into the form, and delivers in 20 minutes. Both appear in the system as translations with the same status. Since B is ten times faster, after six months the corpus consists mostly of B’s work. Statistically, the platform now has more bad translations than good ones—and no error has been recorded anywhere.

*Early warning signal:* Throughput per contributor in words per hour. Anyone far above 3,000 words per hour is not translating but pasting. Second signal: the automatic nuance-screening hit rate per `submitter_id`.

*Mitigation:* Require `translator_id` and `translation_source` (`human | mt_postedit | mt_raw`) for every segment, and use both as ranking signals in retrieval and as labels in the UI. Maintain an ongoing quality metric per contributor using automatic AR/DE screening plus samples reviewed by a second person. New contributors begin in probation: their first ten contributions must go through a second pair of eyes. None of this is distrust; it is the technical implementation of faithful attribution.

### Malicious or ideologically motivated contributor
**organizational** · Severity: critical · Likelihood: medium

*Scenario:* Three realistic variants. (a) Someone removes a condition in translation (“without the ruler’s permission, provided no *fitna* arises”)—the Arabic text remains correct, but the German version, which 95% of users read, is now a different fatwa. (b) Someone uploads genuine audio with an altered transcript; since you do not check every word against the audio, an inserted condition goes unnoticed. (c) Someone deliberately submits only material supporting one faction’s position and shapes the corpus over months—not through a single forgery, but through selection. Variant (c) is hardest to detect and most likely.

*Early warning signal:* For (a) and (b), automatic AR/DE consistency checks flag repeated omitted conditionals from one submitter. For (c), track contributions by scholar and topic per submitter—a sharply skewed distribution at high volume is the signal.

*Mitigation:* Two-person review for everything the AI tool may cite, with two different `submitter_id`s—no exceptions and no self-approval. Full version history (who changed which sentence and when) as an immutable audit log, not a database update. Regularly inspect corpus balance as a chart: contributions per scholar, topic, and contributor. And make one review step mandatory: the reviewer LISTENS to the passage; they do not just read it. Nothing else addresses variant (b).

### Governance vacuum: nobody is religiously accountable, and the inclusion list is itself a position
**organizational** · Severity: critical · Likelihood: almost certain

*Scenario:* Two halves of the same problem. First: until a named brother with recognized *ilm* signs off on the released and precomputed answers, attribution fidelity is just a line in a prompt. If there is such a person, he immediately becomes the bottleneck for everything and the party liable—and he will either fall behind or approve things without adequate review. Second: every decision about which scholar enters the corpus is a *manhaj*-political position in an ongoing schism. Including or excluding a name divides your own team and determines whose material you receive and whose opposition you face—before a single line of code exists.

*Early warning signal:* The first team discussion about whether to include a particular name lasts more than an hour. Second signal: nobody is willing to take named responsibility for the approval decision.

*Mitigation:* Resolve both in writing before the project starts: (1) a named list of included scholars with a short, public criterion—and changes to the list only by a named authority, not by individual decision; (2) a named *muraji* with a limited, realistic workload (e.g. 50 precomputed answers per month)—and the rest of the system must work without him, as an archive only, without synthesis; (3) a formal request for permission and feedback from two or three foundations/editorial offices. Their response—or silence—is the most important signal for the entire project and costs one email.

### Bus factor of 1: one developer across six specialties
**organizational** · Severity: critical · Likelihood: high

*Scenario:* One person is expected to master Arabic ASR and diarization, forced alignment, RAG with cross-lingual retrieval, Next.js with RTL and 150,000 pages, Linux operations with Postgres backups, German media and data-protection law, and volunteer community management. Each is a field of its own. Realistically, one of two things happens: either the project makes no progress on ingestion after three months while the frontend is finished, or the developer becomes unavailable (work, family, exhaustion) and nobody can even keep the system running—a Postgres upgrade, an expired certificate, or a full disk is enough.

*Early warning signal:* The first week with no commit at all. Second signal: an issue stays open for more than two weeks because it falls in an area the developer dislikes.

*Mitigation:* Radically reduce operational workload before building features: managed Postgres instead of self-hosted (the €80–120 annual difference is irrelevant compared with a lost night), ASR via API instead of self-hosted, reranker via API, no Kubernetes, no Temporal, no self-hosted Sentry/Langfuse. Put everything in Docker Compose plus a documented restore procedure that has actually been run and recorded once. Also, give a second person access from day 1 and have them perform the restore themselves, even if they contribute nothing else.

### Deplatforming and the political context in Germany
**legal** · Severity: critical · Likelihood: medium

*Scenario:* A German platform that systematically translates Salafi material and makes it discoverable via AI requires explanation—even if the named scholars are explicitly quietist. A single chunk about *wala wa bara* or takfir presented in isolation in a newspaper article or a report by the Federal Office for the Protection of the Constitution is enough. Then comes the usual chain: the host terminates service, the payment provider disables donations, the domain registrar is contacted, and the association’s bank account is closed. In Germany, this is not hypothetical; it is a documented pattern. All the work can become inaccessible over a weekend.

*Early warning signal:* First press inquiry, first host complaint, or first unusual crawler activity from a government network range. At the latest, a screenshot of one of your answers appears in a context you did not choose.

*Mitigation:* Export-first operations from day 1: content as JSON/JSONL in a Git repository (not only in the database), media in S3-compatible storage, nightly `pg_dump` to a SECOND provider, deployment through Compose/Terraform instead of a managed console, domain with a second registrar account, donations not through a single payment provider. Goal: switching providers takes a weekend, not a redevelopment. In terms of content, topics that can only be read politically do not belong in the corpus—the scope decision in the *Jarh wa Ta'dil* item covers most of them.

### Media law: translated value judgments about living people
**legal** · Severity: high · Likelihood: medium to high

*Scenario:* The corpus contains a recording in which Scholar A says of a named, living person that they are a liar or a *mubtadi*. You translate it into German, make it available, and make it discoverable through AI. Legally, this is no longer third-party content: you translated, curated, and indexed it by topic, so the liability exemption in §§ 7–10 DDG does not apply. If the person concerned resides in Germany, an injunction can follow within days, with costs in the thousands of euros—and without a prior warning if the lawyer chooses that route. This is the most likely legal event for the entire project, more likely than any copyright issue.

*Early warning signal:* An automatic NER pass over the transcripts finds personal names not on your scholar list or transmitter list. Any such hit in an evaluative sentence is a candidate.

*Mitigation:* Run NER on every segment before publication: names outside the curated lists mark the chunk as `not_publishable` until a human decides. For living people, the blanket rule is: no translation, no indexing, no quotation. The operator should be an e.V. or gGmbH with a serviceable address—never a brother’s home address in the legal notice (§ 5 DDG, § 18(2) MStV). Ninety minutes with an IT and media-law attorney before launch costs €300–500 and is the cheapest insurance for the project.

### Art. 9 GDPR: user questions are special-category data—and a target
**legal** · Severity: high · Likelihood: high

*Scenario:* The question “Is music in my profession haram?” reveals the questioner’s religious belief—a special category under Art. 9 GDPR. In practice, only explicit consent applies (point (a)). But you log questions together with IP address and timestamp because you need caching and evaluation. You have therefore built a dataset without a legal basis that (a) can incur fines and (b) can be seized in an investigation concerning third parties. The harm then affects your users, not you—and for a dawah platform, that is reputational damage from which you do not recover.

*Early warning signal:* Look at your own table: if question text is in the same row as an IP address, session ID, or user agent, the mistake has already happened.

*Mitigation:* Resolve the tradeoff consciously; do not ignore it. By default, question text is NOT persisted. For cache and evaluation, a record WITHOUT any identifier is sufficient—question, answer, chunk IDs, scores, timestamp to the nearest day—in a physically separate table that cannot be joined to request logs. Add an opt-in checkbox for anything beyond that. Short TTL for raw logs (24–48 hours). Allow chat without an account. Show a visible AI notice in the chat window from the first interaction (Art. 50 EU AI Act, since 2026-08-02—one sentence in the terms and conditions is explicitly not sufficient).

### LLM costs explode overnight
**financial** · Severity: critical · Likelihood: high

*Scenario:* Four paths, three of them realistic. (a) An actor who opposes the platform sends 500,000 requests through residential proxies; IP rate limiting is ineffective. At about $0.05 per answer, that is $25,000 overnight. (b) Someone exfiltrates the entire corpus through the chatbot—every question is a free RAG dump, and you pay for it. (c) Viral during Ramadan: a post in a large Telegram group brings 50,000 real users in 24 hours; entirely legitimate use, but still a four-figure bill. (d) Prompt injection through the corpus itself: a contributor inserts an instruction in a transcript to generate a very long answer—exploding output tokens and bypassing the citation requirement in one go. Add a quiet multiplier: Arabic tokens cost significantly more than English estimates; your per-answer calculation is probably too low by a factor of 1.5–3.

*Early warning signal:* The provider’s cost alert is too late—it fires after the money is gone. Instead, maintain your own database counter that updates cumulative estimated USD hourly, plus an alert when queries per hour increase tenfold over the previous day.

*Mitigation:* Multiple layers, tested BEFORE launch: (1) A hard daily USD cap in code that disables the synthesis endpoint and serves only the source list—the product remains usable, just without the LLM. (2) Cloudflare Turnstile in front of the chat endpoint. (3) Precomputed top-500 answers that do not call an LLM. (4) `max_tokens` limit. (5) Never embed transcripts as prompt text; pass them as `search_result` blocks, and scan contributor text for instruction patterns before ingestion. (6) Before launch, run a load test with 10,000 requests against your own endpoint and verify that the cap works. (7) Measure actual token costs with `count_tokens` on 20 Arabic transcripts before setting any budget.

### Your own planning assumptions are partly unverified and internally contradictory
**technical** · Severity: high · Likelihood: high

*Scenario:* The research underpinning all architecture and budget decisions marks numerous prices and benchmarks as unverified (Cohere, Jina, Gemini Batch, Hetzner pricing, Fly/Scaleway, Mux). More seriously, two subreports recommend opposing core architectures—one says all three languages must be embedded (cross-lingual recall drops from 92 to 56%), the other says Arabic only, because the original is the source of truth. Both arguments are plausible. In this situation, a small team chooses the option it read first, builds on it for six weeks—and switching an embedder or index means reindexing the entire corpus and invalidating all approved cached answers.

*Early warning signal:* Nobody on the team can say which planning figure was actually checked on a provider’s website. Second signal: an architecture decision is justified with a benchmark number nobody has measured on their own material.

*Mitigation:* Build your own gold set of 100–150 real questions in DE/EN/AR with manually annotated correct fatwa IDs, prepared by two brothers in two afternoons. Then measure the disputed question with 200 videos using both variants—this costs under $20 and replaces every benchmark debate. Store embeddings in a SEPARATE table partitioned by `model_id`, with an `active_embedding_model_id` row, from day 1—then a model change is a partition and a switch, not a project-ending event. Independently verify any price on which more than €50 per month depends directly on the provider’s website before putting it in the budget.

### The AI layer is exactly the part the target audience rejects
**religious/content** · Severity: high · Likelihood: medium to high

*Scenario:* Egypt’s Dar al-Ifta has expressly prohibited AI-assisted tafsir use; IslamQA.info has published its own fatwa against seeking fatwas from AI. The very conservative audience that follows your scholars is least likely to accept a machine between them and the scholar’s words. A realistic outcome: you build for nine months, and the first reactions from the community are not “this is misquoted,” but “one does not ask a machine.” Then the most valuable part (a searchable archive with translated text and precise timestamps) is ready—and the chatbot is the feature that prevents people from using it.

*Early warning signal:* Before building, ask ten people in the target audience whether they would read an AI answer to a fiqh question. You will have the answers in an afternoon.

*Mitigation:* Reverse the order: first build and publish the archive with search and deep links—it is uncontroversially useful, carries no attribution risk, and needs no *muraji*. Add the AI tool afterward, positioned in language and appearance as a search aid, not an answering authority: no fluent chat-style answer, but a list of the positions found, with names, quotations, and videos—the summary is secondary and collapsed. Never position it as a mufti. This is also the wording to use when asking the foundations for permission—and it may determine whether you receive it.
