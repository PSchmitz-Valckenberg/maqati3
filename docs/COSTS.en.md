# Cost Model

*From research, as of 2026-10-07. 1 USD = 0.92 EUR.*

Assumptions: 1 USD = 0.92 EUR, all amounts net. 8 minutes per entry. Arabic token factor conservatively 4 tokens/word — UNVERIFIED; the Claude tokenizer starting from 4.7 generally produces approx. 30% more tokens and the Arabic factor is unmeasured. Measure 20 real transcripts with messages.count_tokens before budget commitment; at 5.5 tokens/word, all translation, embedding, and synthesis line items increase by 37%.

**One-time ingest costs (complete, all three languages indexed)**

| Line item | 70 h (500 entries) | 200 h (1,500) | 400 h (3,000) |
|---|---|---|---|
| ASR Soniox (0.10 USD/h) | 6.44 EUR | 18.40 EUR | 36.80 EUR |
| MT raw translation DE+EN, Haiku Batch | 1.62 EUR | 4.60 EUR | 9.20 EUR |
| Translation QA screening, Haiku Batch | 0.80 EUR | 2.30 EUR | 4.60 EUR |
| Topic tagging, Haiku Batch | 0.32 EUR | 0.97 EUR | 1.93 EUR |
| Embeddings BGE-M3 (RunPod A5000, 0.16 USD/h) | 0.10 EUR | 0.28 EUR | 0.46 EUR |
| Pre-cache 500 Masail x 3 langs., Opus 5.5 Batch | — | 38.64 EUR | 38.64 EUR |
| **One-time total** | **9.28 EUR** | **65.19 EUR** | **91.63 EUR** |

The entire target corpus costs less in ingest than one hour of paid developer time. ASR is not a cost driver in this project. A complete reindex upon changing the embedder costs only the embedding row again, i.e., under 0.50 EUR.

**Ongoing monthly costs**

| Line item | Phase 1: 500 entries, 0 AI questions | Phase 2: 1,500 entries, 10,000 questions, 50% cache | Phase 3: 3,000 entries, 50,000 questions, 65% cache |
|---|---|---|---|
| Server (Hetzner CX, incl. 20% backup + IPv4) | 10.79 (CX33) | 27.38 (CX43+CX33) | 43.37 (CX43+CX43) |
| Hetzner Object Storage (1 TB storage + 1 TB egress incl.) | 6.49 | 6.49 | 6.49 |
| Backblaze B2 cold archive of originals | 0.20 | 0.60 | 1.15 |
| CDN egress audio (Bunny Volume, 0.005 USD/GB) | 0.02 | 0.25 | 1.10 |
| LLM synthesis (Sonnet 5.5, 0.0246 USD per miss) | — | 113.16 | 395.96 |
| Query understanding (Haiku 5.5) | — | 2.76 | 13.80 |
| Verifier (Haiku 5.5) | — | 6.90 | 24.15 |
| Reranking (Voyage rerank-3-lite) | — | 1.38 (Free tier covers approx. 13,000 queries) | 4.83 |
| Domain, TLS, Sentry Free | 1.25 | 2.00 | 3.00 |
| **Total** | **18.75 EUR** | **160.92 EUR** | **493.85 EUR** |

**Comparison figures that justify the decisions**

| Variant | Phase 2 | Phase 3 | Delta |
|---|---|---|---|
| Opus 5.5 instead of Sonnet live | 274.08 | 889.81 | +113 / +396 EUR |
| Without answer cache | 274.08 | 1,169.80 | +113 / +676 EUR |
| Without prompt caching | 214.16 | 680.21 | +53 / +186 EUR |
| Video delivered instead of audio-only | +15.85 | +62.00 | Storage + egress factor 19 |
| Cloudflare Stream instead of object storage | +110.40 | +220.80 | Minute-based billing across the catalog |
| Cohere Rerank 3.5 instead of Voyage lite | +16.50 | +87.20 | Factor 60 |
| Hetzner CCX instead of CX | +75.00 | +150.00 | Price increase 2026-06-15 |

**Interpretation:** Infrastructure costs less than 55 EUR in all three phases. Phase 1 costs under 20 EUR because there is no synthesis — this is the primary reason to build the library before the chatbot. From Phase 2 onwards, over 80% of the invoice is synthesis, which scales with the number of QUESTIONS, not corpus size. Three levers in this order: curated pool (every question from it costs 0 EUR and is simultaneously the better answer because a human approved it), Sonnet instead of Opus, prompt caching. Only after that consider self-hosting — the reranker only breaks even self-hosted starting around 380,000 queries/month.

**Not in this table and larger than everything else:** review effort. 400 h of audio translates to 600–1,200 person-hours for the transcript at 90–180 minutes per audio hour, and with both translations amounts to approx. 4,000 man-hours by the project's own estimate. With ten brothers at four hours per week, that is two years. That is the real cost curve.

[UNVERIFIED: all Hetzner VM prices come from two secondary sources differing by up to 30% (CX23 5.49 vs. 7.13 EUR) because hetzner.com renders prices via JS. Double check in the console before booking. Also unverified: Sentry free tier limit, Bunny Volume pricing for MENA.]

---
## Assumptions

- EXCHANGE RATE: 1 USD = 0.92 EUR. All USD prices from research are converted using this factor. All EUR amounts net (excluding VAT). Hetzner prices are already EUR list prices and are NOT converted.
- AUDIO LENGTH: S1 70 h / 500 videos = 8.4 min; S2 700 h / 5,000 = 8.4 min; S3 4,000 h / 30,000 = 8.0 min. Calculations are consistently based on audio hours, not video count.
- SPEAKING RATE: 130 Arabic words per minute of audio (research assumption from Block 4). 1,000 h = 60,000 min = 7.8M Arabic words.
- ARABIC TOKEN FACTOR: 4 tokens per Arabic word. [UNVERIFIED — research explicitly notes that the Claude tokenizer from 4.7 onwards generally produces approx. 30% more tokens and the Arabic factor is unmeasured. 4 tokens/word is deliberately conservative. Measure 20 real transcripts with messages.count_tokens before budget commitment — if the true factor is 5.5, all translation, embedding, and synthesis line items rise by 37%.] 1,000 h = 31.2M AR tokens.
- CHUNKS: Q&A units instead of fixed token length, approx. 16 AR chunks per 8-min video, times 3 languages. S3 (30,000 videos) = approx. 1.44M vectors, halfvec(1024) = 2 KB x 1.3 HNSW overhead = approx. 3.7 GB index. Fits in 32 GB RAM, so NO dedicated vector DB in any scenario.
- SYNTHESIS PROMPT: 14,000 input tokens per answer (approx. 12–15 AR chunks + translation, system prompt, glossary, scholar-grouped search_result blocks) and 800 output tokens. Research budgeted 11,000/600 — calculated more conservatively here due to the Arabic token premium.
- PROMPT CACHING: 6,000 of the 14,000 input tokens are stable (system prompt, glossary, few-shot, abstain policy) and billed as cache read at 0.05x. 8,000 tokens (retrieved chunks) are fresh per question. Cache write costs amortize starting around 20 questions per 5-minute window and are therefore not individually booked — in S1 with only 2,000 questions/month (approx. 2.8 questions/hour), this amortization is [UNCERTAIN], where the prompt cache benefit is smaller in practice.
- ANSWER CACHE HIT RATE: S1 30%, S2 50%, S3 60% (or 75% in the aggressive pre-caching scenario). Research stated 60–70% — started deliberately lower here because a fatwa corpus requires a strict cache threshold of 0.97 plus a lexical gate due to context dependency (traveler vs. resident, female vs. male), yielding fewer hits than a product FAQ.
- QUERY VOLUME vs. VISITORS: Query expansion (Haiku) runs on ALL questions, synthesis/verifier/reranking only on cache misses.
- MEDIA VOLUMETRICS: Opus 24 kbit/s mono = 0.176 MB/min stored and served. Video ABR ladder (360/480/720p) = 20 MB/min stored, 9 MB/min served (research Block 5). Originals for cold storage: 60 MB per video.
- TRAFFIC ASSUMPTION: 1 playback session per visitor, 5 minutes actually listened to. S1 25,000 min, S2 400,000 min, S3 3,500,000 min served per month.
- ASR: Soniox async 0.10 USD/h as primary pass (diarization included, verified) plus 15% of the corpus in a second pass on Speechmatics Enhanced 0.75 USD/h for legacy cassettes and noisy material (verified). This second pass is the largest single ingest item — without it, ingest is nearly halved.
- HOSTING: Hetzner CX/CAX line (not CPX/CCX following the 2026-06-15 price increase). CX23 5.49 / CX33 8.49 / CX43 15.99 / CX53 29.49 EUR/month. [UNVERIFIED — research explicitly notes that hetzner.com renders prices via JS and was not machine-readable; all Hetzner VM prices stem from two secondary sources differing by up to 30% (CX23 5.49 vs. 7.13 EUR). Cross-check in the console before booking.] Additionally 20% backup surcharge and 0.60 EUR/month IPv4 per VM.
- OBJECT STORAGE: Hetzner Object Storage 6.49 EUR/month incl. 1 TB storage + 1 TB egress, beyond that 8.70 EUR/TB storage and 1 EUR/TB egress. Cold archive of originals on Backblaze B2 at 6.95 USD/TB (verified). CDN: Bunny Volume tier 0.005 USD/GB global flat (verified) — NOT the standard network, where Middle East & Africa costs 0.060 USD/GB, twelve times higher.
- NOT MONETIZED: human review. At 90–180 min review per audio hour, this is S1 105–210 person-hours, S2 1,050–2,100, S3 6,000–12,000. This is the true project bottleneck and appears in none of these calculations because it is volunteer labor. At 15 EUR/h paid labor, S3 would be 90,000–180,000 EUR for this alone.
- NOT INCLUDED: developer time, association founding, legal counsel, tax advice, GPU for potential reranker self-hosting (explicitly not recommended, see Levers).

---
## Largest Levers

- ANSWER CACHE (Lever 1, by far the largest effect). Every percentage point of cache hit rate simultaneously reduces synthesis, verifier, and reranking. S3: hit rate 0% -> 2,715.84 EUR synthesis (Sonnet); 60% -> 2,715.84 x 0.4 = 1,086.34 EUR... or in the calculation above 75% -> 1,697.40 EUR compared to 6,789.60 EUR at 0%. Every percentage point is worth approx. 67 EUR/month in S3. Concretely: 75% instead of 60% saves 1,018 EUR/month. Pre-caching the top 5,000 questions is therefore not primarily a cost measure, but pays double dividends because it is simultaneously the only realistic way to have answers proofread by a brother with 'Ilm BEFORE delivery.
- MODEL CHOICE FOR SYNTHESIS (Lever 2). Sonnet 5.5 instead of Opus 5.5 exactly halves the largest single item: 0.0246 vs. 0.0492 USD per answer. S2: -339.48 EUR/month. S3: -2,715.84 EUR/month at 60% cache. This is not penny-pinching in the wrong place as long as citations are enforced via search_result blocks and verified by the verifier — attribution fidelity comes from architecture, not model size. Recommendation: route by complexity — Sonnet as default, Opus only for questions with detected ikhtilaf across multiple scholars. With 20% Opus share, S3 stands at 2,172 EUR instead of 1,697 EUR (pure Sonnet) or 5,432 EUR (pure Opus).
- PROMPT CACHING (Lever 3). 6,000 of the 14,000 input tokens at 0.05x instead of 1.00x: -31.7% on synthesis costs, a single cache_control parameter. S2: -213 EUR/month with Opus. S3: -850 EUR/month with Sonnet and 75% cache. Prerequisite is a stable system prompt — anyone assembling the glossary dynamically per query destroys the cache hit and only notices on the bill.
- AUDIO INSTEAD OF VIDEO AS DEFAULT DELIVERY (Lever 4, the largest non-LLM lever). Opus 24 kbit/s mono = 0.176 MB/min versus 9 MB/min for video. S3: media costs 9.26 EUR instead of 179.12 EUR, a factor of 19. For fatawa, visuals are almost always a still image or a shaykh at a microphone — information loss is nearly zero, and 24 kbit/s runs on any 2G network in the Maghreb. This is simultaneously an architectural decision, not a later optimization: second-accurate deep links are more reliable on a single progressively served file than on segmented HLS.
- ASR SECOND-PASS RATE (Lever 5, largest ingest lever). The Speechmatics Enhanced second pass on 15% of the corpus costs 103.50 EUR per 1,000 h and thus represents 39% of total ingest. In S3, that is 414 EUR of 1,191 EUR. The rate must be governed by confidence thresholds, not set flat: if the bake-off shows Soniox only degrades at 8% on your material, that halves the item. Conversely: Soniox alone is so cheap at 0.10 USD/h that a complete second pass with another budget provider (instead of Speechmatics) for comparison costs only 92 EUR per 1,000 h.
- BATCH API IN INGEST (Lever 6). Translation, QA, and tagging via the Batch API instead of synchronously: flat -50%. S3: 198 EUR saved one-time. Modest in absolute numbers, but it is a flag, not a refactor — there is no reason not to set it.
- HOSTING CHOICE IS NO LONGER A LEVER, BUT A COST RISK. Hetzner CX line instead of CPX/CCX following the 2026-06-15 price hike (CCX23 jumped from 31.49 to 85.99 EUR, a 2.73x factor). Booking CCX out of habit means paying approx. 280 EUR in server costs for S3 instead of 104.46 EUR. That is 175 EUR/month — more than total media delivery in audio mode. Yet compared to 1,700 EUR in synthesis, even that is background noise.
- DO NOT SELF-HOST THE RERANKER. Voyage rerank-3-lite costs 20.70 EUR/month in S3; a dedicated A5000 for bge-reranker-v2-m3 costs 116.80 USD = 107.46 EUR/month. The reranker is the one component where the API remains substantially cheaper even in the large scenario — and it remains swappable at any time because changing rerankers is one configuration line with no reindexing needed.

---
## Where the Bill Explodes

- ARABIC TOKEN FACTOR HIGHER THAN 4/WORD. The entire calculation rests on this single unmeasured number. At 5.5 tokens/word, translation, contextual retrieval, embeddings, AND the 14,000 input tokens per synthesis rise by 37%. S3 would then be approx. 2,700 instead of 2,060 EUR/month, ingest approx. 1,550 instead of 1,190 EUR. SAFEGUARD: run 20 real transcripts through messages.count_tokens before budget commitment and measure the factor. That is one hour of work; otherwise, it shifts every number here.
- CACHE HIT RATE REMAINS BELOW 30%. The threshold of 0.97 plus lexical gate (Jaccard >= 0.8) is deliberately strict because a single word flips the answer in this corpus (musafir vs. muqim, negation). If the true distribution of questions is very broad, the cache remains cold. S3 without cache on Sonnet: 6,789.60 EUR synthesis instead of 1,697.40 EUR. SAFEGUARD: pre-caching from actual queries of the first weeks plus a curated list of classical masail; cache hit rate as a dashboard metric from Day 1; if below 40% after 4 weeks, re-evaluate model choice instead of buying more servers.
- BOT OR SCRAPER FLOODS THE CHAT ENDPOINT. A single attacker with 100,000 long questions overnight generates 100,000 x 0.0741 USD = 7,410 USD = 6,817 EUR on Opus. That is the most realistic way to destroy this project overnight, and rate limiting by IP is bypassable. SAFEGUARD (four-tier, not single): (1) hard daily EUR cap in code that shuts down the endpoint — not provider billing alerts, which only trigger once money is already spent; (2) Cloudflare Turnstile in front of the endpoint; (3) max_tokens ceiling on input AND output; (4) semantic cache preventing identical floods from reaching the model in the first place.
- VIRAL MOMENT. A video by a well-known da'i referencing the platform can multiply traffic tenfold overnight. Under video delivery, S3 x 10 would mean 307 TB of egress = 1,538 USD = 1,415 EUR in a single month. SAFEGUARD: audio-only as default (the same 10x is then only 27.70 EUR), plus Cloudflare R2 as hot origin where egress costs structurally zero — this is insurance, not optimization.
- GEMINI PRICE DOUBLING ON 2027-01-01 (officially announced: Flash 0.75 -> 1.50 input, 3.75 -> 7.50 output). Budgeting around current Flash prices doubles costs in Phase 2. Similarly: gpt-5.6-sol is promo pricing until 2026-11-21 according to research [UNVERIFIED]. SAFEGUARD: place model calls behind a dedicated interface with three roles (synthesize, cheap_task, verify) — switching providers is then a single config line, not a rewrite.
- EMBEDDING MODEL SWITCH WITH WRONG SCHEMA. Re-indexing itself costs almost nothing (55 EUR in S3). It becomes expensive only if embeddings live as a column on the chunk table instead of a table partitioned by model_id — switching then means downtime, dual-writing, and worst-case rollback while the chatbot serves answers from a half-migrated index. SAFEGUARD: embedding(chunk_id, model_id, vec) plus app_config.active_embedding_model_id from Day 1, CREATE INDEX CONCURRENTLY, toggle via config value.
- ASR ON REAL MATERIAL MUCH WORSE THAN IN BENCHMARK. The cited 6.5–10.8% WER stems from FLEURS (cleanly read studio MSA). Legacy cassettes with room reverb and Najdi dialect sit at 20–40%. That does not break the ASR bill (which stays at 0.10 USD/h), but the review bill: instead of 90 min per audio hour, it becomes 180+, and in S3 that is 12,000 person-hours instead of 6,000. SAFEGUARD: measure WER on 20 real clips BEFORE corpus targets are set; architect so that unreviewed material is visibly flagged and never output as a verbatim quotation; prioritize review by retrieval hits instead of working through the corpus linearly.
- CLOUDFLARE STREAM OR MUX INSTEAD OF GB-BASED BILLING. In S3 (240,000 catalog minutes), Cloudflare Stream alone costs 240,000 / 1,000 x 5 USD = 1,200 USD = 1,104 EUR per month for STORAGE ALONE before anyone watches anything. Mux would be 720 USD = 662 EUR. This is a silent project killer because the invoice grows with archive size, not usage. SAFEGUARD: strictly GB-based providers (Bunny, R2, Hetzner Object Storage, B2).
- HETZNER HIKES PRICES AGAIN. 2026 already brought a 2.2–2.7x increase on CPX/CCX. Legacy rates remain grandfathered per announcement — but only until the next rescale, exactly when scaling up. SAFEGUARD: deployment via Docker Compose / Terraform instead of managed consoles, making provider switches a weekend project; export-first anyway, because deplatforming is a tangible risk for this content category.
- GOOGLE DRIVE INGEST DIES ON QUOTAS OR SERVICE ACCOUNT TRAPS. Costs no money, but weeks of developer time — and developer time in a one-person team is the most expensive resource in the project. Service accounts have no storage of their own (403 storageQuotaExceeded without Shared Drive and therefore without Google Workspace), watch channels expire after 1 or 7 days without auto-renew, and since 2026-05-01 new projects face a different quota model than test projects. SAFEGUARD: changes.list polling with persisted startPageToken instead of watch channels, and migrate as early as possible to a custom presigned-URL form — where scholar_id and source_url can be technically enforced, resolving the core religious concern at the same time.

---
## Cheapest Viable Path

CHEAPEST VIABLE PATH — viable in terms of attribution fidelity, not just price.

PHASE 1 (0–500 videos): approx. 25 EUR one-time + 85 EUR/month
A single Hetzner CX33 (8.49 EUR) carries app, worker, Postgres with pgvector and pg_search, plus Redis. Audio-only as default delivery from Day 1 — this is not a cost-saving measure to retrofit later, but an architectural decision accounting for a 19x media cost factor in S3. ASR via Soniox (0.10 USD/h), translation segmented with Haiku 5.5 via Batch API, embeddings with BGE-M3 on a rented GPU for a few hours, reranking via Voyage rerank-3-lite within the 200M free allowance (covers the entire beta for free). Synthesis with Opus 5.5, because at 1,400 answers/month the 63 EUR is well worth it and the initial answers serve as the template for all subsequent ones. Prompt caching from the outset, even if it saves only 51% at 2,000 questions — the code for it should be in place when volume arrives.

THE ONLY EXPENSE YOU CANNOT AFFORD TO SKIP HERE: the 20-clip bake-off of ASR providers on your real material. Thanks to Speechmatics starting credits (100 USD) and Gladia (50 EUR), it costs virtually nothing, yet it determines the review burden of the next three years — the only metric in this entire model measured in person-years rather than euros.

PHASE 2 (up to 5,000 videos): approx. 210 EUR one-time + 434 EUR/month
Here lies the single decision dominating everything else: switch synthesis from Opus to Sonnet 5.5 once the citation pipeline (search_result blocks, verifier with attribution check against scholar_id) has proven that fidelity stems from architecture rather than model size. That cuts 679 EUR in half to 339 EUR. Simultaneously bring the answer cache to 50%. Three VMs instead of one, because request latency, batch CPU, and database have distinct load profiles. Monitoring on self-hosted GlitchTip. Still no dedicated vector database, no Qdrant, no Meilisearch — at 240,000 vectors, that would be pure operational overhead and, worse, a secondary state that can drift from the review state.

PHASE 3 (up to 30,000 videos): approx. 1,190 EUR one-time + 2,060 EUR/month
Sonnet as default with Opus routing only for detected ikhtilaf, cache hit rate to 75% via pre-caching the top 5,000 questions with a human approval step. Four VMs, audio-only, Bunny Volume CDN. 2,060 EUR/month is significant for a donor-funded project, but achievable — and 82% of it is a single item, synthesis, directly tied to utility. Total infrastructure costs 156 EUR.

HOW TO RECOGNIZE THE PATH: Every phase shares the exact same shape. One Postgres, one object storage, audio instead of video, Batch API in ingest, prompt cache and answer cache throughout, reranker via API instead of self-hosted, and a model interface with three roles so providers remain swappable. What changes between phases is not architecture, but simply instance sizing and synthesis model.

WHAT MONEY CANNOT BUY: Ingest for 4,000 h costs 1,190 EUR and is thus cheaper than one week of developer time. Human review of that same material takes 6,000–12,000 person-hours, meaning between one and a half and three years for 20 active volunteers at 4 h/week. That is the true cost curve of this project, and it appears in no table above. Every architectural decision should be evaluated by whether it reduces this number — prioritize review by retrieval hits, translate segment-by-segment rather than freely (halves effort per entry), substitute Quranic verses via lookup from canonical text rather than having reviewers correct them, and visibly flag unreviewed material instead of withholding it. A system that only functions with a fully reviewed corpus will never go live.
