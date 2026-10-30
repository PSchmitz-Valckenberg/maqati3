# Risks

*From the adversarial critic agent.*

## Kill Shots — what realistically ends the project

- The translation and review workload is one to two orders of magnitude larger than the volunteer team. 1,000 audio hours realistically cost 20,000–25,000 person-hours (correction at 20–40 percent WER plus MT post-editing in two target languages plus review). With 20 volunteers working 4 hours per week, that is 5–6 years for one-fifth of the target corpus. It is not the technology that fails, but the volume assumption. Anyone planning for 50,000 videos is planning for 160,000–200,000 person-hours.

- A single publicized misattribution destroys the platform permanently. Trust in this field is binary: one misattributed audio clip, one shifted nuance in a talaq or takfir question, one screenshot in a large group — and the platform is forever "the site that put words into Ibn Baz's mouth." Technically fixable, socially irreversible. The risk scales linearly with corpus size and falls with review density — exactly the resource that is lacking.

- Bus factor 1 across six required specialized disciplines (Arabic ASR, forced alignment, cross-lingual RAG, RTL frontend with a six-figure page count, Linux ops, German media and data privacy law) plus community management. The project does not die from a bug, but from the exhaustion of a single person — after which no one can even keep the system running.

- Governance vacuum: without a named brother with Ilm bearing religious responsibility, the product is irresponsible; with him, he becomes the bottleneck and the liability subject. Even the list of included scholars represents a manhaj-political positioning within an ongoing sectarian conflict — it divides the team before any code exists and dictates who will provide material and who will push back.

- The AI layer is precisely the component that the conservative target audience rejects (islamqa has a fatwa against AI fatawa, Dar al-Ifta issued a ban). It is entirely possible to build for nine months only to hear "one does not consult a machine" rather than "this is misquoted." The valuable part — the searchable archive — is complete, and the chatbot is the exact reason it goes unused.

- Legal and political deplatforming in Germany: an isolated chunk on takfir or wala' wa bara' cited in a press article, followed by a chain reaction from the host, payment provider, and domain registrar. In addition, the single most probable legal event: an interim injunction over a translated statement concerning a living person residing in Germany. Without a registered association (Verein) as the legal entity and without an export-first architecture, both represent existential threats.

- The corpus is correct and the answers are nevertheless false, because oral fatawa are situation-dependent and your data model does not capture this. No model, reranker, or verifier resolves this — only mandatory fields for question text, occasion, date, and generality level assigned by a human. Hence, this point also hinges on the workforce calculation in Kill Shot 1.

---
## Defuse first

- Throughput measurement instead of estimation (1 afternoon, 0 EUR): three volunteers, each given 30 minutes of real target audio, full run with a stopwatch — ASR correction, German translation, review by a second person. Multiply the result by the actual available weekly capacity. This single number decides the entire corpus target size, and it will likely decide against 50,000 videos. Planning anything else before obtaining this number is wasted time.
- Attribution sampling in raw material (1 day, 0 EUR): have 30 random clips currently circulating on Telegram/YouTube as fatawa of the named scholars audited against binbaz.org.sa, binothaimeen.net, and alifta.gov.sa by a qualified expert. What is the misattribution rate? If it exceeds 10 percent, the community upload path as a primary source is dead and you may only ingest from official sources — which changes the entire ingest architecture and saves months.
- Adversarial question set BEFORE building (2 days, under 50 USD): write 50 questions designed to break the system — negations, "did Sheikh X ever say", minimal pairs (traveler vs. resident), comparison queries, takfir, first-person talaq, scholar vs. scholar, thinly covered topics, time-bound questions. Then build a throwaway prototype with 50 videos and a frontier model, ask the 50 questions, and have them evaluated by a brother with Ilm. This tells you in week 1 whether the product concept is viable — not in month 9.
- Translation nuance testing (1 day, 0 EUR): run 20 sentences containing makruh/haram, la yanbaghi, al-ahwat, fihi tafsil, and conditional clauses through MT and through two volunteers. Count how often legal nuances flip. More than 20 percent means: pure post-editing is insufficient, the legal ruling must be recorded separately as a controlled enum — worsening the workforce calculation in point 1 even further.
- Authority and permission inquiry (one email): send a one-page concept in Arabic to two or three foundations and editorial offices (binothaimeen.net, miraath.net, al-Fawzan's office) requesting permission and feedback on the idea. The response — or silence — is the single most important signal of the entire project: without it, the project lacks both legal and religious backing, and binothaimeen.net has already set an explicit TDM opt-out in its robots.txt. Frame your platform as an index and search tool within the words of the scholars, never as a mufti.
- Legal assessment before writing a single line of production code (90 minutes, 300–500 EUR): consult an IT and media/defamation lawyer on three questions: institutional entity structure and imprint, liability for translated remarks concerning living persons, and GDPR Article 9 implications for account-less chat. This is the cheapest insurance for the project and prevents the two most probable legal hazards.
- Spending cap test and timestamp integrity test in CI from Day 1 (half a day each): execute 10,000 requests against your own endpoint to verify that the daily hard cap genuinely triggers before anything goes public. In parallel, build a cron job that picks 50 random chunks, re-verifies the audio from start_ms via ASR, and alerts if match rate falls below 70 percent — plus a canary row with state=pending that runs hourly to test whether the review filter remains in the retrieval path. Both are the sole defense mechanisms against the two quietest failure modes.
- Document scope decisions in writing (1 meeting): determine which scholars to include, which topics to EXCLUDE (Jarh wa Ta'dil, rulings on specific individuals, talaq, inheritance, takfir, vows), who the Muraji' (reviewer) is, and what realistic monthly commitment they can offer. These three determinations are not bureaucracy — they define the data schema, the intent classifier, and the liability posture. Making them retroactively means building the corpus twice.

---
## Full Risk List

### Synthetic fatwa produced by cross-merging two scholars
**content-religious** · Severity: critical · Probability: almost certain without structural countermeasure

*Scenario:* Question: Is the duff permissible at a wedding? Retrieval returns 4 chunks from Ibn Baz (permissibility for women during the walima) and 3 from al-Albani (hadith transmission context, conditioned on no men listening). The model writes: "The scholars permit the duff at weddings, provided that no men are present." Every clause is backed by a chunk, every citation is properly linked — yet this fatwa exists in the works of neither scholar. The condition originates from A, the permission from B, and A never attached that condition to this ruling. Entailment checking fails to catch this because each individual sentence is entailed. The user acts on it and attributes it to Ibn Baz.

*Early warning signal:* In a test run of 50 questions, answers contain collective phrasing without specific names: "the scholars", "there is consensus", "in the view of the scholars." Every occurrence is a match.

*Countermeasure:* Structural, not prompt-based. (1) One evidence block per scholar; chunks from different scholars never enter the same block. (2) Answer schema lacks any field for a collective opinion — only a list of positions, each containing exactly one scholar_id, a dalil field, and at least one quote. If there is no schema field for it, the model cannot write it. (3) Verifier inspects attribution alignment: if an al-Albani chunk_id supports a statement attributed to Ibn Baz, the answer fails. (4) Regex blocklist for collective expressions as a final barrier.

### Situation-dependent fatwa output as a general rule
**content-religious** · Severity: critical · Probability: almost certain

*Scenario:* A questioner spends two minutes explaining his situation: he lives in the West, has no other job, and his family depends on it. The scholar replies in 40 seconds: "In your specific case, there is no harm in it." Your chunking splits on the Q/A boundary, retrieval fetches exactly those 40 seconds, and the deep link points directly there. The system outputs: "Sheikh X permits working at a bank; source: video, minute 14:20." The qualifying hardship and the follow-up question ("but continue seeking alternative employment") are missing from the chunk. This is not a model defect, but a data model flaw — and it affects the vast majority of audio fatawa, as spoken answers are almost always delivered for a specific case.

*Early warning signal:* In a sample of 30 answers, more than one third of cited chunks cannot be determined as either general or case-specific from the chunk text alone. This is measurable without live users.

*Countermeasure:* Mandatory fields in the schema, not the prompt: `question_text_ar` (full text of the inquirer's question), `context_note` (occasion, location, broadcast, year), `generality` (`general` | `case_specific` | `unclear`, set by the reviewer, defaulting to `unclear`). Retrieval rule: chunks where `generality != general` may only be served if the questioner's original question is included and rendered above the answer in the UI. Deep links must always start 20 seconds BEFORE the chunk, never at its exact beginning. Where `generality = unclear`, disable synthesis entirely and provide only a direct link to the video.

### A scholar's retraction (Ruju') remains invisible
**content-religious** · Severity: critical · Probability: high (rises with corpus size)

*Scenario:* Al-Albani revised his hadith gradings on multiple occasions (shifts between Silsilat al-Da'ifah and al-Sahihah); Ibn 'Uthaymeen retracted positions on specific masa'il. In your corpus lie a 1988 cassette tape and a 1997 lecture, both addressing the exact same topic. Retrieval selects the older recording because it has higher semantic relevance (formulated more distinctly, fewer subordinate clauses). The system cites a stance that the scholar himself retracted — accompanied by name, date, and deep link, making it appear maximally authoritative. No retrieval algorithm can solve this on its own, because the fact that a ruju' occurred is not stated in the text.

*Early warning signal:* Two chunks from the same scholar on the same topic separated by > 3 years with contradictory rulings. This can be detected automatically once `scholar_id`, date, and topic are cleanly recorded — and forms the exact review list that a reviewer must inspect.

*Countermeasure:* Introduce `supersedes` / `superseded_by` fields at the chunk level alongside a `ruju_known` flag. Automated conflict detector: identical scholar, identical topic, conflicting ruling keywords -> trigger entry into a review queue; until reviewed, display BOTH references side by side with dates and omit any AI synthesis. The date thus becomes a mandatory schema field, not a nice-to-have: an undated audio file must not be cited in conflicting matters. In reality, only a human with Ilm can resolve this — keep the conflict list manageable by growing the corpus in depth rather than broad width.

### Misattributed audio circulating in public (incl. AI voice clones)
**content-religious** · Severity: critical · Probability: high

*Scenario:* A well-meaning brother uploads an MP3 file that has circulated in Telegram groups for years under Ibn Baz's name. In reality, it is a student speaking, or another sheikh with a similar voice on a noisy cassette. It gets stored with `scholar_id=ibn-baz` in a database claiming religious authority, gets transcribed, translated, chunked, precomputed, cached — and republished by other platforms because you are now the most accessible source. 2026 variant: an adversary deliberately generates a voice-cloned audio file. Public training material is available across hundreds of hours, and a platform claiming authority is the exact target where such an attack pays off. The damage is irreversible because the misinformation propagates outward.

*Early warning signal:* Sampling test: have 30 circulating clips verified by a domain expert against binbaz.org.sa / binothaimeen.net / alifta.gov.sa. If the misattribution rate in raw material exceeds 10 percent, community uploads as a primary source are dead.

*Countermeasure:* Provenance classes in the schema instead of blind trust: `provenance = official_site | verified_broadcast | unverified_community_upload`. Only the first two classes may be cited by the AI tool; `unverified_community_upload` remains browseable in the library with an explicit warning banner and zero citation permissions. A `source_url` pointing to an official domain is mandatory for citation eligibility. In addition: automate transcript cross-matching against official text corpora — where matching text is confirmed, attribution is validated; where not, it remains unverified. This is the only scalable attribution test available.

### Translation inverts legal nuance (karahah vs. tahrim, dropped conditions)
**content-religious** · Severity: critical · Probability: almost certain

*Scenario:* The scholar states *la yanbaghi* ("it is not befitting") or *al-ahwat tarkuhu* ("the more cautious path is to leave it") or *makruh* (disliked). The volunteer — or DeepL — writes: "it is forbidden" (haram). Conversely, *la yajuz* ("it is not permissible") gets translated as "it is better to avoid." Or the most frequent failure mode: *fihi tafsil* ("there is detail/distinction to be made here") is dropped because the translator assumes the subsequent subordinate clause is redundant, turning a conditional permission into an unconditional absolute. This translation enters the German index, gets matched by retrieval, ranked top by the reranker, and quoted by the LLM. While the Arabic original sits next to it, the German-speaking user — who visited precisely for the translation — will never read the Arabic.

*Early warning signal:* Conduct a targeted test on 20 sentences containing these exact linguistic patterns using MT and two volunteers. If legal nuances flip in more than 20 percent of cases, simple post-editing is inadequate.

*Countermeasure:* Controlled ruling vocabulary instead of unconstrained translation: the translator translates the text, but the RULING itself is recorded separately as an enum (`wajib` | `mustahabb` | `mubah` | `makruh` | `haram` | `fihi_tafsil` | `no_ruling`) and displayed in the UI as its own dedicated label, never extracted from prose. Enforce a glossary of hard equivalents (300–500 term pairs) that appears as autocompletion in the review UI and triggers warnings upon divergence. Second safeguard: an automated Haiku batch screening that compares the Arabic original and German translation in a single prompt, verifying only ruling severity and dropped conditionals — costing fractions of a cent per clip and intercepting this failure class reliably.

### Weaponization in sectarian conflicts (Jarh wa Ta'dil, scholar against scholar)
**content-religious** · Severity: critical · Probability: almost certain

*Scenario:* A user submits: "What did Sheikh X say about Sheikh Y?" or "Provide evidence that Z is an innovator (*mubtadi*)." In a Salafi corpus, this is not an edge case — an entire genre of audio recordings exists around this, and they rank among the most frequently searched. Your tool delivers curated, translated ammunition at the press of a button, sorted by relevance, with deep links. Within weeks, the platform becomes co-opted by one faction and attacked by others. Contributors fragment, the claim of neutrality is shattered, and material is submitted selectively to canonize partisan stances. Furthermore: if Y is a living individual residing in Germany, you are republishing a translated defamatory factual assertion as your own platform content.

*Early warning signal:* The first 200 real queries already feature questions of this category. They manifest immediately, not late — visible in the closed beta query log well before public launch.

*Countermeasure:* Scope determination BEFORE building, not moderation after: personal evaluations (*Jarh wa Ta'dil*) must never enter the corpus — introduce a distinct `content_class` field applied during ingest, and exclude that class from indexing entirely. Deploy an intent classifier on queries (lightweight model, 0.0002 USD) that detects queries regarding rulings on individuals and rejects them with a fixed static message rather than performing retrieval. This forfeits a portion of the audience and preserves the project — the reverse does not hold.

### Life-altering individual cases (Talaq, inheritance, vows, Takfir) answered generically
**content-religious** · Severity: critical · Probability: almost certain

*Scenario:* A user types: "I uttered talaq three times, what is the ruling now?" This is one of the most common reasons individuals seek out fatwa websites. Your system retrieves fatawa on triple talaq, identifies conflicting positions, summarizes them briefly — and the user acts on it. However, a marital fatwa depends heavily on precise phrasing, the wife's state, intent, and prior occurrences; without diagnostic follow-up questions, any answer is erroneous. The exact same vulnerability applies to inheritance division, solemn vows (*qasam*), ribawi financial contracts, and — most dangerously — takfir questions ("has my father become a kafir?"). This is also the exact category of inquiries that a journalist or authority tests first.

*Early warning signal:* Query logs: inquiries phrased in the first person recounting specific personal circumstances instead of abstract general rulings. Measure this proportion during the initial weeks — it will be higher than anticipated.

*Countermeasure:* Topic blocklist with hard routing instead of synthesis: Talaq, inheritance law, vows/oaths, Takfir, Khul', and personal medical decisions. On these topics, the system must NEVER provide a synthesized AI response; it may only return search citations accompanied by a mandatory static notice: *"This is an individual case requiring direct consultation with a scholar or qualified local imam."* Detection relies on the intent classifier combined with first-person pronoun heuristics. This is technically simple and constitutes the single most important safety guardrail of the entire platform.

### Proving a negative: "Did Sheikh X ever state that..."
**Retrieval failure** · Severity: high · Probability: almost certain

*Scenario:* Question: "Did Ibn Baz ever say that demonstrations are permissible?" Your system finds nothing, and accurately responds: "No records found on this matter." The user interprets this as: "He never said it" — takes a screenshot, and circulates it on social media as proof. Yet your corpus covers perhaps 2 percent of the scholar's total lifetime body of work. The system structurally lacks any capacity to prove non-existence, but the UI implies completeness because it presents as an archive. The identical failure emerges in comparative questions: 8 chunks retrieved for scholar A, 0 for scholar B, and the answer implies that scholar B never commented on the topic.

*Early warning signal:* In the adversarial question set: every query structured as "has X ever...", "is there a fatwa from X on...", or "what is the difference between X and Y." Check whether the generated response makes assertions of absence.

*Countermeasure:* Absence is never an assertion regarding the scholar, but solely regarding the corpus — and must be explicitly formulated verbatim: *"This archive currently holds no recordings from Sheikh X on this specific question. The archive currently contains N recordings from him and is not exhaustive."* Include a visible coverage indicator on every scholar profile (N recordings, M hours, topical domains). Filter queries of the form "did X ever say" via the intent classifier and bypass synthesis entirely. For comparison queries: perform isolated retrieval for each referenced scholar and display the match count per scholar transparently.

### Negation and minimal pairs break retrieval AND caching
**Retrieval failure** · Severity: critical · Probability: high

*Scenario:* "Is image editing permissible?" and "Is image editing forbidden?" sit exceptionally close in embedding space — dense vector models are notoriously weak at handling negation. The issue is even more pronounced with minimal pairs that completely alter the legal verdict: *Musafir* (traveler) vs. *Muqim* (resident), *Ha'id* (menstruating) vs. *Tahir* (pure), gold as personal jewelry vs. financial investment, with *Niyyah* (intention) vs. without. Two queries exhibiting 0.97 cosine similarity carry opposing rulings. The semantic cache then serves the stored response of the incorrect question — and does so for months, as nothing invalidates it. This results in a cached false fatwa equipped with genuine citations.

*Early warning signal:* Construct 30 minimal pairs (single-phrase difference, diametrically opposed rulings) and execute them against the cache. Any instance where query pair A retrieves the cached result for pair B is a production failure.

*Countermeasure:* Cache hit allowed only when cosine similarity >= 0.97 AND lexical gating succeeds: extracted content keywords of both queries must achieve Jaccard similarity >= 0.8, and a curated dictionary of discriminator tokens (traveler, resident, menses, jewelry, investment, intention, not, no, without) must match identically, else trigger a cache miss. The cache key must always incorporate `(lang, model_id, corpus_version)`. Sample 50 cache hits weekly for manual audit — an incorrect cache hit here is not just a poor search result, but a misattributed religious edict.

### Sparse coverage with marginal threshold matches — more dangerous than zero matches
**Retrieval failure** · Severity: high · Probability: almost certain

*Scenario:* The primary hazard is not a complete absence of matches (where an abstain rule fires), but the marginal threshold zone: two or three weak chunks scoring just above the cutoff. Example: a query regarding cryptocurrencies. The corpus contains no direct fatwa on the matter, but includes an offhand remark on *Gharar* in a 1994 lecture on commerce. The reranker promotes it because it represents the highest scoring match available. Armed with citations, scholar name, and timestamps, the generated answer appears more authoritative than any standard search engine result — yet constitutes an extrapolation the scholar never made. This represents the most frequent form of actual real-world harm and eludes verifiers because the text is technically supported by the chunk.

*Early warning signal:* Plot the distribution of reranker top-1 scores across real production queries. The intermediate band is the hazard zone. If more than 20 percent of queries land in this band, the threshold is miscalibrated.

*Countermeasure:* Two thresholds instead of one: above the upper threshold, permit AI synthesis; between the lower and upper threshold, return ONLY raw source citations without AI synthesis, accompanied by an explicit note stating that the found records only tangentially touch upon the topic; below the lower threshold, return nothing. In addition, introduce topic coverage verification: if the query topic does not align with curated topic tags for which the corpus holds verified material, enforce a hard abstain regardless of vector score. You already maintain this topic catalog for the library anyway.

### Speaker role confusion (questioner vs. scholar) — question cited as fatwa
**technical** · Severity: critical · Probability: medium to high

*Scenario:* Diarization segments speakers A and B; the heuristic "longest talk time = scholar" fails precisely in recordings where the questioner delivers an elaborate, detailed background — typical in classic radio fatwa broadcasts. The questioner's inquiry often contains a faulty premise: *"Sheikh, some people claim that X is permissible, arguing that..."* If this passage is indexed as a scholar segment, your system cites the adversarial premise as the scholar's own verdict — the exact opposite of reality. Featuring correct timestamps, correct scholar attribution, and working deep links.

*Early warning signal:* Audit sample of 50 chunks marked with `speaker_role=scholar`: if any begins with standard questioner honorifics (*yaqul as-sa'il*, *fadilat ash-shaikh*, *ahsana Allahu ilaik*, *su'ali huwa*), the role assignment is erroneous. This can be monitored continuously as an automated check.

*Countermeasure:* Speaker role must be a mandatory field confirmed by human review, never derived solely from automated heuristics. Only chunks with `speaker_role=scholar` AND `role_confirmed=true` are eligible for citation. Implement formula detection as an automated bidirectional pre-filter (questioner formulas in scholar segments and answer formulas in questioner segments). Index questioner segments separately as question text — these are valuable for retrieval since user queries resemble them — but assign them a distinct type that is never served as a scholar's answer.

### Timestamp drift — the quietest failure of the entire architecture
**technical** · Severity: critical · Probability: high

*Scenario:* Three independent root causes: (a) ffmpeg cuts with `-ss` placed before `-i`, resulting in served media files offset by 0.3 to 2 seconds; (b) a volunteer omits filler words or condenses verbal repetitions during transcription, causing forced alignment to drift by seconds or minutes downstream without throwing an error; (c) ctc-forced-aligner receives Arabic text without uroman romanization and outputs zero-timestamps across the board. In all three instances, everything appears functional: the web page loads, quotes are visible, links are clickable. However, the user lands in the middle of a response to a DIFFERENT question. Nobody notices because nobody clicks every single citation, and users who do assume they misheard. This destroys the foundational trust upon which the entire product relies.

*Early warning signal:* A cron job active from Day 1: randomly sample 50 chunks, re-run 10 seconds of audio starting from `start_ms` through ASR, and fuzzy-match the output against the first words of the transcript chunk. Any match below 70 percent triggers an immediate alert. In addition, strictly reject any segment where `t_start == t_end == 0` or timestamps fail to advance monotonically.

*Countermeasure:* Persist `align_confidence` per segment; below the acceptable threshold, the deep link is DEACTIVATED rather than jumping inaccurately (no jump is far better than a wrong jump). Always align timestamps against the SERVED delivery media file, never against the raw archival master, verified via automated CI tests. The ASR run serves as the ground truth for timing, while human-edited text governs wording — joined via text-to-text alignment rather than acoustic forced alignment on raw audio.

### `review_state` dropped from retrieval pipeline — unreviewed raw MT cited as evidence
**technical** · Severity: critical · Probability: medium

*Scenario:* During refactoring of the hybrid search query, the `state='approved'` filter gets omitted from the SQL `WHERE` clause — for instance, when someone adds an optimized scan path for selective filters and neglects to copy the condition over. Following that deployment, the AI tool quotes raw, unvetted machine translations as the exact words of the scholar. Nothing crashes, nothing logs an error, and answers may even appear subjectively "better" due to a larger candidate pool. The bug is only discovered when external users expose an inaccurate translation publicly.

*Early warning signal:* Canary row: place a designated dummy chunk in the database with `state='pending'` containing a unique marker string. An hourly cron job submits the query designed to trigger it, sounding an alert if the marker string ever surfaces in retrieval results or generated answers.

*Countermeasure:* Canary row coupled with database-level isolation rather than application-level filtering: create a dedicated view `chunks_citable` containing the review filter, and restrict the application database user to have SELECT permissions ONLY on that view, with zero SELECT rights on the underlying base table. This prevents the condition from ever being forgotten in code. In addition: every served chunk must include its `review_state` in the API payload, and the frontend must display a visible error banner if an unapproved chunk is encountered.

### Translation and editing workload exceeds volunteer capacity by 1–2 orders of magnitude
**organizational** · Severity: critical · Probability: almost certain

*Scenario:* Quantitative reality for 1,000 audio hours (roughly 6,000–7,500 clips of 8–10 minutes): Arabic word count: 1,000 h × 60 min × 130 words/min ≈ 7.8 million words. Transcript editing at a realistic 20–40 percent WER on vintage cassette audio: 90–180 minutes per audio hour, amounting to 1,500–3,000 person-hours. Translation: a professional translator completes 2,000–2,500 words per eight-hour workday; MT post-editing yields 6,000–8,000 words — representing 975 to 3,900 person-days per target language. With MT post-editing across two target languages: roughly 15,000–20,000 person-hours, plus approximately 3,000 hours for review and QA. Total realistic workload: 20,000–25,000 person-hours for 1,000 audio hours. With 20 active volunteers committing 4 hours weekly, this requires 250–310 weeks (5 to 6 years) to process just one-fifth of the target collection. For the full 8,300-hour archive: 160,000–200,000 person-hours. This is not tight; it is mathematically impossible.

*Early warning signal:* Measure in Week 1 rather than estimating: three volunteers, 30 minutes of audio each, full end-to-end run timed with a stopwatch. Multiply the resulting hours-per-audio-hour by your total realistic capacity. Second signal: weekly throughput drops by more than 50 percent between Week 1 and Weeks 4–6.

*Countermeasure:* Corpus target size is the primary control lever, not tooling. Specifically: (1) Cap the target corpus at 300–800 meticulously curated fatawa addressing the top 50 most searched masa'il — prioritize depth over breadth. A complete, impeccably verified archive covering Taharah and Salah is infinitely more valuable and credible than 50,000 partially checked clips. (2) Prioritize human review based on actual retrieval hits: only passages appearing in live top-k results get queued for manual vetting. (3) Where official textual fatawa already exist (binbaz.org.sa, alifta), apply text-to-audio alignment rather than scratch transcription, eliminating the single largest cost center. (4) The software architecture must natively handle unreviewed material: clearly tagged, never quoted verbatim, and never ingested into the AI generator.

### Volunteer churn after three months — project stalls in an intermediate state
**organizational** · Severity: critical · Probability: high

*Scenario:* The standard open-source trajectory: initial excitement, a Ramadan peak, followed by steep attrition. After four months, 3,000 videos have been ingested, 400 reviewed, and 2,600 linger in the database with raw machine translations. The project faces two bad alternatives: display unreviewed content (severe attribution risk) or hide it (the platform feels empty despite months of work, and remaining volunteers see no impact). The project becomes structurally too large to audit and too small to be useful — permanently stranded in limbo.

*Early warning signal:* Track weekly active contributor counts. If the metric declines two consecutive weeks, the drop-off curve has begun. Second signal: the ratio of ingested to reviewed videos exceeds 3:1.

*Countermeasure:* Ingest throttle: enforce a strict rule in the admin UI allowing new videos into ingest only in proportion to what was reviewed in the same week (maximum ratio of 2:1). This may feel counterintuitive, but it saves the project. Combine this with motivational transparency: a public status portal showing the journey of every submission from receipt to publication, with contributor attribution (for those who desire it). Break work into small, self-contained milestone batches (one chapter, ten fatawa) rather than an infinite backlog — completing a defined topic gives a sense of accomplishment, an endless queue does not.

### Quality variance across contributors — the least rigorous produces the most volume
**organizational** · Severity: high · Probability: almost certain

*Scenario:* Brother A is a native Arabic speaker with formal Islamic knowledge (Ilm); he spends 3 hours per audio hour and delivers meticulous translations. Brother B has two years of beginner Arabic; he pastes DeepL output directly into the submission form and finishes in 20 minutes. Both submissions enter the system marked with identical status. Because Brother B works ten times faster, the corpus consists predominantly of Brother B's material after six months. Statistically, the platform accumulates far more low-quality translations than high-quality ones — without a single explicit error being logged anywhere.

*Early warning signal:* Measure contributor throughput in words per hour. Anyone significantly exceeding 3,000 words per hour is pasting rather than translating. Second signal: detection rates from automated nuance screenings grouped by `submitter_id`.

*Countermeasure:* Make `translator_id` and `translation_source` (`human` | `mt_postedit` | `mt_raw`) mandatory segment-level attributes, utilizing both as ranking features in retrieval and displaying them transparently as UI badges. Maintain continuous quality metrics per contributor derived from automated AR/DE screening and peer spot-checks. New contributors begin in probationary status: their first ten submissions require mandatory dual-review. None of this is distrust; it is the technical implementation of attribution fidelity.

### Malicious or ideologically motivated contributor
**organizational** · Severity: critical · Probability: medium

*Scenario:* Three realistic attack vectors: (a) A contributor deletes a qualifying condition during translation ("without permission of the ruler, provided no fitnah arises") — the Arabic original remains intact, but the German text read by 95 percent of users is transformed into an entirely different ruling. (b) A contributor uploads authentic audio paired with a manipulated transcript; because you cannot listen to every word, an inserted secondary clause goes unnoticed. (c) A contributor systematically submits only material supporting a specific factional viewpoint, subtly shaping the corpus over several months without falsifying a single text, merely through selective curation. Variant (c) is the hardest to detect and the most probable.

*Early warning signal:* For (a) and (b): automated AR/DE consistency checks report an elevated frequency of missing conditional clauses from a specific submitter. For (c): analyze distribution of submissions across scholars and topics per submitter — a heavily skewed distribution at high volume is a key indicator.

*Countermeasure:* Mandatory four-eyes principle (dual sign-off) for everything eligible for AI citation, requiring two distinct `submitter_id`s — with zero exceptions and no self-approval. Comprehensive immutable audit logging (recording who modified which sentence and when) rather than in-place database updates. Regularly inspect corpus balance charts: submissions per scholar, per topic, per contributor. And an indispensable review step: the auditor must actively LISTEN to the audio passage, not merely read the text — nothing else protects against vector (b).

### Governance vacuum: no religious accountability, and the scholar inclusion list is itself partisan
**organizational** · Severity: critical · Probability: almost certain

*Scenario:* Two facets of the same dilemma. First: unless a named brother with recognized Islamic knowledge (Ilm) signs off on approved and precomputed answers, attribution fidelity is merely a line in a prompt. If such an individual exists, he immediately becomes the operational bottleneck for everything and the sole target of public liability — leading him either to fall behind or rubber-stamp submissions. Second: every decision regarding which scholars to include in the corpus constitutes a manhaj-political positioning in an ongoing sectarian dispute. Including or omitting a specific name divides your own team and dictates who provides content and who mounts opposition — before a single line of code is written.

*Early warning signal:* The first internal discussion regarding the inclusion of a specific scholar lasts longer than one hour. Second signal: no team member is willing to take named personal responsibility for sign-off decisions.

*Countermeasure:* Resolve both aspects in writing before project initiation: (1) Publish an explicit, named list of included scholars accompanied by brief, public inclusion criteria — with modifications governed solely by a designated body, not ad-hoc decisions. (2) Appoint a designated Muraji' with a defined, realistic monthly workload (e.g., 50 precomputed answers per month) — ensuring the remainder of the platform operates reliably without him, serving strictly as an archive without AI synthesis. (3) Issue formal written requests for permission and guidance to two or three established foundations/editorial boards. Their reply — or lack thereof — represents the single most vital signal for the project and costs only an email.

### Bus factor 1: a single developer across six specialized domains
**organizational** · Severity: critical · Probability: high

*Scenario:* One individual is expected to master: Arabic ASR and diarization, forced alignment, RAG with cross-lingual retrieval, Next.js with RTL layout across 150,000 pages, Linux operations with Postgres backups, German media and data protection law, plus community volunteer management. Each domain is an entire discipline in itself. Realistically, one of two outcomes occurs: either the project stalls after three months in the data ingest pipeline while the frontend is already finished, or the developer becomes unavailable (work, family commitments, burnout) and nobody is equipped to keep the system operational — a Postgres upgrade, an expired TLS certificate, or a full disk drive is enough to take the entire service down.

*Early warning signal:* The first week with zero repository commits. Second signal: a ticket remains unresolved for more than two weeks simply because it falls into an area the primary developer dislikes.

*Countermeasure:* Radically minimize operational overhead before building new features: opt for managed Postgres rather than self-hosting (an 80–120 EUR annual difference is negligible compared to a lost night of debugging), consume ASR via managed APIs rather than self-hosted models, use reranker APIs, avoid Kubernetes, Temporal, and self-hosted Sentry/Langfuse instances. Package everything into Docker Compose backed by a documented, verified restore procedure that has been executed and logged in practice. Furthermore: grant access credentials to a second team member from Day 1 and have them run the full restore process independently, even if they contribute nothing else.

### Deplatforming and the political landscape in Germany
**legal** · Severity: critical · Probability: medium

*Scenario:* A German platform systematically translating Salafi material and making it discoverable via AI requires careful explanation — even if the featured scholars are explicitly quietist. An isolated chunk addressing Wala' wa Bara' or Takfir cited in a newspaper article or intelligence report is sufficient to trigger the standard escalation chain: the hosting provider terminates service, the payment processor suspends donation channels, domain registrars receive formal inquiries, and bank accounts are shut down. In Germany, this is not a theoretical scenario, but a well-documented pattern. Months of work can be rendered unreachable over a single weekend.

*Early warning signal:* First media inquiry, initial complaint forwarded by the hosting provider, or unusual crawler activity originating from government network blocks. At the very latest: a screenshot of a generated response appearing in an unvetted external context.

*Countermeasure:* Adopt an export-first architecture from Day 1: store content as JSON/JSONL in a Git repository (not solely inside a database), keep media assets in S3-compatible object storage, execute nightly pg_dump backups to a SECOND independent provider, define infrastructure in Docker Compose/Terraform rather than manual console settings, register domains across separate registrar accounts, and diversify donation processing. Goal: transitioning providers should take a single weekend, not a rebuild. Content-wise: topics that are interpreted purely politically must not enter the corpus — the scope boundaries established under the Jarh wa Ta'dil policy address the vast majority of these concerns.

### Defamation and media law: translated value judgments regarding living individuals
**legal** · Severity: high · Probability: medium to high

*Scenario:* The corpus contains a recording in which scholar A refers to a named, living person as a liar or an innovator (*mubtadi*). You translate this into German, publish it, and make it searchable via AI. Legally, this is no longer third-party content: you have translated, curated, and indexed the material — voiding liability privileges under §§ 7–10 DDG (German Digital Services Act). If the affected individual resides in Germany, an interim injunction can follow within days, incurring four-figure legal fees without prior warning if the attorney so chooses. This constitutes the single most probable legal event of the entire project — far more likely than copyright litigation.

*Early warning signal:* Run an automated Named Entity Recognition (NER) pass across transcripts to locate person names that do not appear in your approved scholar catalog or canonical narrator lists. Every match located within an evaluative sentence context is an immediate flag.

*Countermeasure:* Mandatory NER screening prior to publishing any segment: person names outside approved reference lists flag the chunk as `unpublishable` until human review occurs. For living individuals, apply a strict blanket rule: no translation, no indexing, no citations. Establish a registered association (e.V.) or non-profit GmbH with a valid legal address as the operating entity — never publish the private residential address of an individual in the website imprint (§ 5 DDG, § 18 para. 2 MStV). A 90-minute consultation with an IT and defamation attorney before launch costs 300–500 EUR and provides the cheapest insurance for the project.

### GDPR Article 9: user queries constitute special category data — and an attractive target
**legal** · Severity: high · Probability: high

*Scenario:* An inquiry such as "Is music in my job forbidden?" directly reveals the religious beliefs of the user — qualifying as special category personal data under Article 9 GDPR. In practice, only explicit consent (Art. 9(2)(a)) provides a valid legal basis. If you log search queries alongside IP addresses and timestamps for caching and evaluation, you construct a database without lawful justification that is (a) subject to administrative fines and (b) subject to subpoena and seizure in investigations involving third parties. The harm directly impacts your users rather than just the platform — causing irreversible reputational damage for a da'wah initiative.

*Early warning signal:* Inspect your database schema: if question text shares the same row as IP addresses, session IDs, or user agents, the violation has already occurred.

*Countermeasure:* Consciously resolve the trade-off rather than ignoring it: by default, do NOT persist query text. For caching and evaluation, maintain records devoid of all identifiers — question, answer, chunk IDs, similarity scores, and date truncated to day-level precision, housed in a physically distinct table that cannot be joined with server request logs. Provide an opt-in checkbox for any logging beyond this baseline. Enforce short retention TTLs on raw web logs (24–48 hours). Allow chat access without requiring user registration. Display a clear, prominent AI transparency banner in the chat interface from the very first interaction (mandated by Article 50 EU AI Act since August 2, 2026 — an obscure line in the terms of service is explicitly insufficient).

### Overnight LLM cost explosion
**financial** · Severity: critical · Probability: high

*Scenario:* Four failure pathways, three of which are common realities. (a) A hostile actor targeting the platform fires 500,000 requests via residential proxies, rendering IP rate-limiting ineffective. At roughly 0.05 USD per response, this racks up 25,000 USD in a single night. (b) An external party scrapes the entire corpus through the chat interface — each query functions as a free RAG dump financed by your account. (c) A viral surge during Ramadan: a link shared in a large Telegram group drives 50,000 legitimate users within 24 hours, generating four-figure API bills. (d) Prompt injection embedded directly within the corpus: a malicious contributor writes an instruction into a transcript commanding the model to produce extremely lengthy output — inflating output token usage while bypassing citation requirements. Compounding factor: Arabic tokens incur significantly higher token counts than English estimates, making baseline cost projections per answer 1.5–3x too low.

*Early warning signal:* Provider billing alerts arrive too late — they trigger only after credit is consumed. Instead: maintain an internal database counter tracking cumulative estimated USD hourly, paired with an automated alert if hourly query volume multiplies tenfold compared to the prior day.

*Countermeasure:* Multi-layered defenses tested prior to public launch: (1) Hard daily spending ceiling in USD enforced in code, automatically shutting down the generative synthesis endpoint and falling back to returning raw citation lists — keeping the product usable without LLM charges. (2) Deploy Cloudflare Turnstile ahead of chat endpoints. (3) Precompute top-500 common queries to avoid invoking LLM models. (4) Configure strict `max_tokens` limits. (5) Never embed transcripts directly as unstructured prompt text; wrap them in structured `search_result` blocks and scan incoming contributor text for instruction syntax prior to ingest. (6) Execute load tests simulating 10,000 requests against endpoints before launch to verify that the spending cap engages. (7) Measure empirical token consumption using `count_tokens` across 20 Arabic transcripts before locking down budget plans.

### Foundational planning documentation is partially unverified and internally inconsistent
**technical** · Severity: high · Probability: high

*Scenario:* The background research supporting architectural and budgetary decisions marks numerous pricing points and benchmarks as unverified (Cohere, Jina, Gemini Batch, Hetzner hosting, Fly/Scaleway, Mux). More critically: two foundational reports recommend diametrically opposed core retrieval strategies — one advocates embedding across all three languages (warning of cross-lingual recall dropping from 92 to 56 percent), while the other insists on embedding Arabic exclusively because the original language is the source of truth. Both arguments have merit. In such circumstances, a small team often defaults to whichever document it read first, invests six weeks of engineering, and faces a costly dead end — switching embedding models or index architectures requires reindexing the entire corpus and invalidates all precomputed cached answers.

*Early warning signal:* No team member can verify whether specific figures in the plan were checked directly against current provider pricing. Second signal: an architectural decision is justified using a benchmark metric that nobody has measured against your own project data.

*Countermeasure:* Compile a dedicated gold evaluation dataset of 100–150 authentic questions across German, English, and Arabic with manually annotated correct fatwa IDs, created by two team members over two afternoons. Then benchmark the disputed architectural options using 200 videos across both variants — costing under 20 USD and settling the debate empirically. Partition vector embeddings in a dedicated table by `model_id` alongside an `active_embedding_model_id` configuration row from Day 1 — allowing model upgrades to be executed via simple partition switching without project disruption. Individually verify every pricing line item exceeding 50 EUR monthly against provider portals before incorporating it into budgets.

### The AI layer is precisely the component that the target audience rejects
**content-religious** · Severity: high · Probability: medium to high

*Scenario:* Dar al-Ifta of Egypt has expressly prohibited AI-driven tafsir tools; islamqa.info published a formal fatwa advising against soliciting fatawa from artificial intelligence. The conservative audience following these traditional scholars is precisely the demographic least willing to accept a machine intermediary between themselves and the scholar's words. Realistic outcome: after nine months of development, initial reactions from the community are not "this is misquoted," but "one must not consult a machine." At that point, the most valuable asset — a searchable, accurately timecoded, translated archive — is complete, but the chatbot feature actively deters the community from using it.

*Early warning signal:* Before writing code, ask ten individuals from the target audience whether they would read an AI-generated synthesis answering a fiqh question. You will have your answer in an afternoon.

*Countermeasure:* Invert the roadmap sequence: build and launch the searchable archive with deep links first — this is undeniably beneficial, carries zero attribution risk, and requires no supervising Muraji'. Introduce the AI assistant later, positioning it visually and linguistically strictly as a search companion rather than an answering authority: present no fluent chat-style prose, but rather a structured list of retrieved rulings with scholar names, exact citations, and video player links — keeping synthesis optional and collapsed by default. Never position the system as a mufti. This is also the exact wording to use when requesting official permission from scholarly foundations — determining whether permission is granted.
