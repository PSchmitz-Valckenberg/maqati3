# Cost Model

*From research, as of 2026-10-07. 1 USD = 0.92 EUR.*

Assumptions: 1 USD = 0.92 EUR, all amounts net. 8 minutes per entry. Arabic token factor conservatively 4 tokens/word — UNVERIFIED; the Claude tokenizer from version 4.7 onwards generally produces approx. 30% more tokens and the Arabic factor is unmeasured. Before committing budget, measure 20 real transcripts with `messages.count_tokens`; at 5.5 tokens/word, all translation, embedding, and synthesis line items increase by 37%.

**One-time Ingest Costs (complete, all three languages indexed)**

| Line item | 70 h (500 entries) | 200 h (1,500) | 400 h (3,000) |
|---|---|---|---|
| ASR Soniox (0.10 USD/h) | 6.44 EUR | 18.40 EUR | 36.80 EUR |
| MT raw translation DE+EN, Haiku Batch | 1.62 EUR | 4.60 EUR | 9.20 EUR |
| Translation QA screening, Haiku Batch | 0.80 EUR | 2.30 EUR | 4.60 EUR |
| Topic tagging, Haiku Batch | 0.32 EUR | 0.97 EUR | 1.93 EUR |
| Embeddings BGE-M3 (RunPod A5000, 0.16 USD/h) | 0.10 EUR | 0.28 EUR | 0.46 EUR |
| Pre-cache 500 Masail x 3 lang., Opus 5.5 Batch | — | 38.64 EUR | 38.64 EUR |
| **Total one-time** | **9.28 EUR** | **65.19 EUR** | **91.63 EUR** |

The entire target corpus costs less in ingest than one hour of paid developer time. ASR is not a cost driver in this project. A complete reindex when switching embedders costs only the embedding line again, i.e., under 0.50 EUR.

**Monthly Operating Costs**

| Line item | Phase 1: 500 entries, 0 AI questions | Phase 2: 1,500 entries, 10,000 questions, 50% cache | Phase 3: 3,000 entries, 50,000 questions, 65% cache |
|---|---|---|---|
| Server (Hetzner CX, incl. 20% backup + IPv4) | 10.79 (CX33) | 27.38 (CX43+CX33) | 43.37 (CX43+CX43) |
| Hetzner Object Storage (1 TB storage + 1 TB egress incl.) | 6.49 | 6.49 | 6.49 |
| Backblaze B2 cold archive of originals | 0.20 | 0.60 | 1.15 |
| CDN audio egress (Bunny Volume, 0.005 USD/GB) | 0.02 | 0.25 | 1.10 |
| LLM synthesis (Sonnet 5.5, 0.0246 USD per miss) | — | 113.16 | 395.96 |
| Query understanding (Haiku 5.5) | — | 2.76 | 13.80 |
| Verifier (Haiku 5.5) | — | 6.90 | 24.15 |
| Reranking (Voyage rerank-3-lite) | — | 1.38 (Free tier covers approx. 13,000 queries) | 4.83 |
| Domain, TLS, Sentry Free | 1.25 | 2.00 | 3.00 |
| **Total** | **18.75 EUR** | **160.92 EUR** | **493.85 EUR** |

**Comparative Figures Justifying Key Decisions**

| Variant | Phase 2 | Phase 3 | Delta |
|---|---|---|---|
| Opus 5.5 instead of live Sonnet | 274.08 | 889.81 | +113 / +396 EUR |
| Without response cache | 274.08 | 1,169.80 | +113 / +676 EUR |
| Without prompt caching | 214.16 | 680.21 | +53 / +186 EUR |
| Video delivered instead of audio-only | +15.85 | +62.00 | Storage + egress factor 19 |
| Cloudflare Stream instead of Object Storage | +110.40 | +220.80 | Minute billing applied to catalog |
| Cohere Rerank 3.5 instead of Voyage lite | +16.50 | +87.20 | Factor 60 |
| Hetzner CCX instead of CX | +75.00 | +150.00 | Price increase 2026-06-15 |

**Interpretation:** Infrastructure costs less than 55 EUR across all three phases. Phase 1 costs under 20 EUR because there is no synthesis — this is the primary reason to build the library before the chatbot. From Phase 2 onwards, over 80% of the bill is synthesis, which scales with the number of QUESTIONS, not corpus size. Three levers in this order: curated pool (every question from it costs 0 EUR and is simultaneously a better answer because a human approved it), Sonnet instead of Opus, prompt caching. Only consider self-hosting after that — a self-hosted reranker only breaks even above approx. 380,000 queries/month.

**Not in this table and larger than everything else:** human review effort. 400 h of audio at 90–180 minutes per audio hour means 600–1,200 person-hours for the transcript, and with both translations according to the project's own calculations, approx. 4,000 man-hours. With ten contributors at four hours per week, that is two years. That is the true cost curve.

[UNVERIFIED: all Hetzner VM prices originate from two secondary sources that differ by up to 30% (CX23 5.49 vs. 7.13 EUR) because hetzner.com renders prices via JS. Verify in the Console prior to booking. Also unverified: Sentry Free tier limit, Bunny Volume price for MENA.]

---
## Assumptions

- EXCHANGE RATE: 1 USD = 0.92 EUR. All USD prices from research are converted using this factor. All EUR amounts net (excluding VAT). Hetzner prices are already EUR list prices and are NOT converted.
- AUDIO LENGTH: S1 70 h / 500 videos = 8.4 min; S2 700 h / 5,000 = 8.4 min; S3 4,000 h / 30,000 = 8.0 min. Calculations consistently use audio hours, not video count.
- SPEAKING RATE: 130 Arabic words per audio minute (research assumption from Block 4). 1,000 h = 60,000 min = 7.8M Arabic words.
- ARABIC TOKEN FACTOR: 4 tokens per Arabic word. [UNVERIFIED — research explicitly notes that the Claude tokenizer from version 4.7 onwards generates approx. 30% more tokens and the Arabic factor is unmeasured. 4 tokens/word is deliberately conservative. Before committing budget, measure 20 real transcripts with `messages.count_tokens` — if the true factor is 5.5, all translation, embedding, and synthesis line items increase by 37%.] 1,000 h = 31.2M AR tokens.
- CHUNKS: Q&A units rather than fixed token length, approx. 16 AR chunks per 8-min video, multiplied by 3 languages. S3 (30,000 videos) = approx. 1.44M vectors, halfvec(1024) = 2 KB x 1.3 HNSW overhead = approx. 3.7 GB index. Fits in 32 GB RAM, meaning NO dedicated vector DB in any scenario.
- SYNTHESIS PROMPT: 14,000 input tokens per response (approx. 12–15 chunks AR+translation, system prompt, glossary, scholar-grouped `search_result` blocks) and 800 output tokens. Research estimated 11,000/600 — I calculate more conservatively due to the Arabic token markup.
- PROMPT CACHING: 6,000 of the 14,000 input tokens are stable (system prompt, glossary, few-shot, abstain policy) and billed as cache read at 0.05x. 8,000 tokens (retrieved chunks) are fresh per question. Cache write costs amortize starting around 20 questions per 5-minute window and are therefore not booked separately — with S1 at only 2,000 questions/month (approx. 2.8 questions/hour), this amortization is [UNCERTAIN], where the prompt cache advantage is smaller in practice.
- RESPONSE CACHE HIT RATE: S1 30%, S2 50%, S3 60% (or 75% in the aggressive pre-caching scenario). Research cited 60–70% — I start deliberately lower because a Fatwa corpus requires a strict cache threshold of 0.97 plus lexical gate due to context dependence (traveler vs. resident, female vs. male), yielding fewer hits than a product FAQ.
- QUERY VOLUME vs. VISITORS: Query expansion (Haiku) runs on ALL questions; synthesis/verifier/reranking only runs on cache misses.
- MEDIA QUANTITY STRUCTURE: Opus 24 kbit/s mono = 0.176 MB/min stored and delivered. Video ABR ladder (360/480/720p) = 20 MB/min stored, 9 MB/min delivered (research Block 5). Originals for cold storage: 60 MB per video.
- TRAFFIC ASSUMPTION: 1 playback session per visitor, 5 minutes actually listened. S1 25,000 min, S2 400,000 min, S3 3,500,000 min delivered per month.
- ASR: Soniox async 0.10 USD/h as primary pass (diarization included, verified) plus 15% of corpus in a second pass on Speechmatics Enhanced 0.75 USD/h for legacy cassette tapes and noisy recordings (verified). This second pass is the single largest ingest line item — without it, ingest is nearly halved.
- HOSTING: Hetzner CX/CAX line (not CPX/CCX after the 2026-06-15 price increase). CX23 5.49 / CX33 8.49 / CX43 15.99 / CX53 29.49 EUR/month. [UNVERIFIED — research explicitly notes that hetzner.com renders prices via JS and was not machine-readable; all Hetzner VM prices come from two secondary sources differing by up to 30% (CX23 5.49 vs. 7.13 EUR). Verify in the Console prior to booking.] Additionally 20% backup markup and 0.60 EUR/month IPv4 per VM.
- OBJECT STORAGE: Hetzner Object Storage 6.49 EUR/month incl. 1 TB storage + 1 TB egress; beyond that 8.70 EUR/TB storage and 1 EUR/TB egress. Cold archive of originals on Backblaze B2 at 6.95 USD/TB (verified). CDN: Bunny Volume tier 0.005 USD/GB global flat (verified) — NOT the standard network, where Middle East & Africa costs 0.060 USD/GB (twelve times higher).
- NOT MONETIZED: human review. At 90–180 min review per audio hour, this represents S1 105–210 person-hours, S2 1,050–2,100, S3 6,000–12,000. This is the true project bottleneck and appears in none of these financial calculations because it is volunteer work. At 15 EUR/h paid labor, S3 alone would require 90,000–180,000 EUR.
- NOT INCLUDED: developer time, legal incorporation, legal counsel, tax advice, GPU for potential reranker self-hosting (explicitly not recommended, see Levers).

---
## Largest Levers

- RESPONSE CACHE (Lever 1, by far the largest effect). Every percentage point of cache hit rate simultaneously reduces synthesis, verifier, and reranking. S3: hit rate 0% -> 2,715.84 EUR synthesis (Sonnet); 60% -> 2,715.84 x 0.4 = 1,086.34 EUR... or in calculation above, 75% -> 1,697.40 EUR compared to 6,789.60 EUR at 0%. Each percentage point at S3 is worth approx. 67 EUR/month. Concretely: 75% instead of 60% saves 1,018 EUR/month. Pre-caching the top 5,000 questions is therefore not primarily a cost measure, but pays off twofold because it is simultaneously the only realistic way to have answers proofread by a human with knowledge BEFORE delivery.
- MODEL SELECTION FOR SYNTHESIS (Lever 2). Sonnet 5.5 instead of Opus 5.5 cuts the largest single line item exactly in half: 0.0246 vs. 0.0492 USD per answer. S2: -339.48 EUR/month. S3: -2,715.84 EUR/month at 60% cache. This is not cutting corners as long as citations are enforced via `search_result` blocks and verified by the verifier — attribution faithfulness stems from architecture, not model size. Recommendation: route by complexity — Sonnet as default, Opus only for questions with detected Ikhtilaf across multiple scholars. With a 20% Opus share, S3 sits at 2,172 EUR instead of 1,697 EUR (pure Sonnet) or 5,432 EUR (pure Opus).
- PROMPT CACHING (Lever 3). 6,000 of the 14,000 input tokens at 0.05x instead of 1.00x: -31.7% on synthesis costs, a single `cache_control` parameter. S2: -213 EUR/month with Opus. S3: -850 EUR/month with Sonnet and 75% cache. Prerequisite is a stable system prompt — dynamically assembling the glossary on every request breaks the cache hit and is only noticed on the bill.
- AUDIO INSTEAD OF VIDEO AS DEFAULT DELIVERY (Lever 4, largest non-LLM lever). Opus 24 kbit/s mono = 0.176 MB/min versus 9 MB/min with video. S3: media costs 9.26 EUR instead of 179.12 EUR, a factor of 19. For Fatawa, the visual is almost always a static slide or a speaker at a microphone — information loss is practically zero, and 24 kbit/s runs on any 2G network across the Maghreb. This is simultaneously an architectural decision, not a later optimization: second-accurate deep links are more reliable with a single progressively delivered file than with segmented HLS.
- ASR SECOND-PASS RATIO (Lever 5, largest ingest lever). The Speechmatics Enhanced second pass on 15% of the corpus costs 103.50 EUR per 1,000 h and constitutes 39% of total ingest. For S3, this is 414 EUR out of 1,191 EUR. The quota must be driven by confidence thresholds rather than set blanketly: if bake-offs reveal Soniox on your material only becomes critical at 8%, that halves this line item. Conversely: Soniox alone at 0.10 USD/h is so economical that a complete second pass with another budget provider (instead of Speechmatics) for comparison costs only 92 EUR per 1,000 h.
- BATCH API IN INGEST (Lever 6). Translation, QA, and tagging via Batch API instead of synchronous requests: blanket -50%. S3: 198 EUR saved one-time. Small in absolute figures, but it is a flag, not a refactor — there is no reason not to set it.
- HOSTING CHOICE IS NO LONGER A LEVER, BUT A COST RISK. Hetzner CX line instead of CPX/CCX following the 2026-06-15 price increase (CCX23 rose from 31.49 to 85.99 EUR, a factor of 2.73). Defaulting to CCX out of habit costs approx. 280 EUR in server expenses at S3 instead of 104.46 EUR. That is 175 EUR/month — more than the entire media delivery in audio mode. Yet compared to 1,700 EUR synthesis, this too is noise.
- DO NOT SELF-HOST THE RERANKER. Voyage rerank-3-lite costs 20.70 EUR/month at S3; a dedicated A5000 for bge-reranker-v2-m3 costs 116.80 USD = 107.46 EUR/month. The reranker is the one component where the API remains noticeably cheaper even in large scenarios — and it is replaceable at any time because swapping rerankers is a single config line and triggers no reindexing.

---
## Where Costs Explode

- ARABIC TOKEN FACTOR EXCEEDING 4/WORD. The entire calculation hinges on this single unmeasured number. At 5.5 tokens/word, translation, Contextual Retrieval, embeddings, AND the 14,000 input tokens per synthesis increase by 37%. S3 would then be approx. 2,700 instead of 2,060 EUR/month; ingest approx. 1,550 instead of 1,190 EUR. SAFEGUARD: before committing budget, run 20 real transcripts through `messages.count_tokens` and measure the factor. That is one hour of work and otherwise shifts every figure here.
- CACHE HIT RATE REMAINS BELOW 30%. The threshold of 0.97 plus lexical gate (Jaccard >= 0.8) is deliberately strict because in this corpus a single word flips the ruling (musafir vs. muqim, negation). If actual question distribution is very broad, the cache stays empty. S3 without cache on Sonnet: 6,789.60 EUR synthesis instead of 1,697.40 EUR. SAFEGUARD: pre-caching from actual queries of early weeks plus a curated list of classical Masail; cache hit rate as a dashboard metric from Day 1; if it remains below 40% after 4 weeks, re-evaluate model selection rather than buying more servers.
- BOT OR SCRAPER FLOODS CHAT ENDPOINT. A single attacker submitting 100,000 lengthy questions overnight produces 100,000 x 0.0741 USD = 7,410 USD = 6,817 EUR with Opus. This is the most realistic way to destroy this project overnight, and rate-limiting by IP is easily bypassed. SAFEGUARD (fourfold, not single): (1) hard daily spending cap in EUR in code that disables the endpoint — not provider billing alerts that fire only after money is spent; (2) Cloudflare Turnstile in front of the endpoint; (3) `max_tokens` ceiling on BOTH input and output; (4) semantic cache preventing identical flood requests from reaching the model at all.
- VIRAL MOMENT. A video from a prominent Da'i referencing the platform can multiply traffic tenfold overnight. With video delivery, S3 x 10 equals egress of 307 TB = 1,538 USD = 1,415 EUR in a single month. SAFEGUARD: audio-only by default (the same 10x is then only 27.70 EUR), plus Cloudflare R2 as hot origin where egress structurally costs zero — this is not an optimization, but an insurance policy.
- GEMINI PRICE DOUBLING ON 2027-01-01 (officially announced: Flash 0.75 -> 1.50 input, 3.75 -> 7.50 output). Building a budget on current Flash rates doubles costs in Phase 2. Similarly: gpt-5.6-sol is promo pricing until 2026-11-21 according to research [UNVERIFIED]. SAFEGUARD: place model invocations behind a dedicated interface with three roles (`synthesize`, `cheap_task`, `verify`) — switching providers is then a config line, not an architectural rewrite.
- EMBEDDING MODEL MIGRATION WITH INCORRECT SCHEMA. Reindexing itself costs almost nothing (55 EUR at S3). It becomes expensive only if embeddings reside as a column on the `chunk` table rather than in a table partitioned by `model_id` — a change then implies downtime, dual-writing, and potentially rollback while the chatbot serves answers from a half-migrated index. SAFEGUARD: `embedding(chunk_id, model_id, vec)` plus `app_config.active_embedding_model_id` from Day 1, `CREATE INDEX CONCURRENTLY`, toggle via config value.
- REAL-WORLD ASR MUCH WORSE THAN BENCHMARK. Cited 6.5–10.8% WER figures originate from FLEURS (clean studio-recorded MSA). Older audio tapes with room reverb and Najdi dialect sit at 20–40%. This blows up not the ASR invoice (which remains at 0.10 USD/h), but the review invoice: instead of 90 min per audio hour, it becomes 180+, and for S3 that is 12,000 person-hours instead of 6,000. SAFEGUARD: measure WER on 20 real clips BEFORE fixing corpus targets; construct architecture so unverified content is clearly labeled and never output as a verbatim citation; prioritize review by retrieval hits rather than working through the corpus linearly.
- CLOUDFLARE STREAM OR MUX INSTEAD OF GB-BASED BILLING. For S3 (240,000 catalog minutes), Cloudflare Stream costs 240,000/1,000 x 5 USD = 1,200 USD = 1,104 EUR per month purely for STORAGE before anyone views content. Mux would be 720 USD = 662 EUR. This is a silent project killer because invoices scale with archive size rather than usage. SAFEGUARD: use exclusively GB-based providers (Bunny, R2, Hetzner Object Storage, B2).
- HETZNER RAISES PRICES AGAIN. 2026 already saw a 2.2–2.7x hike on CPX/CCX. Legacy pricing is grandfathered according to announcements — but only until the next rescale, exactly when scaling up. SAFEGUARD: deploy as Docker Compose / Terraform rather than managed console so switching providers takes a weekend; export-first regardless, since deplatforming is a genuine risk for this content domain.
- GOOGLE DRIVE INGEST DIES ON QUOTAS OR SERVICE ACCOUNT TRAPS. Costs no money, but weeks of developer time — and developer time in a single-person team is the most expensive resource. Service accounts have no independent storage (`403 storageQuotaExceeded` without Shared Drive and thus without Google Workspace), watch channels expire after 1 or 7 days without auto-renewal, and since 2026-05-01 new projects face a different quota model than test projects. SAFEGUARD: `changes.list` polling with persisted `startPageToken` instead of watch channels, and migrate as early as possible to a custom presigned-URL submission form — where `scholar_id` and `source_url` are technically enforceable, solving the core religious integrity requirement simultaneously.

---
## Cheapest Viable Path

CHEAPEST VIABLE PATH — viable in the sense of attribution faithfulness, not merely price.

PHASE 1 (0–500 videos): approx. 25 EUR one-time + 85 EUR/month
A single Hetzner CX33 (8.49 EUR) hosts app, worker, Postgres with `pgvector` and `pg_search`, and Redis. Audio-only as default delivery from Day 1 — this is not a savings measure retrofitted later, but an architectural decision that accounts for a factor of 19 in media costs at S3. ASR via Soniox (0.10 USD/h), segment-wise translation with Haiku 5.5 via Batch API, embeddings with BGE-M3 on a rented GPU for a few hours, reranking via Voyage rerank-3-lite under the 200M free allowance (which carries the entire beta at zero cost). Synthesis with Opus 5.5 because at 1,400 answers/month, 63 EUR is well worth it and early responses set the template for all subsequent ones. Prompt caching from the start even if saving only 51% at 2,000 questions — the code should be established before volume arrives.

THE SINGLE EXPENSE NOT TO SKIMP ON HERE: the 20-clip bake-off across ASR providers on your actual recordings. Thanks to Speechmatics starter credits (100 USD) and Gladia (50 EUR) it costs practically nothing, yet it determines the review burden of the next three years — the only dimension in this entire model measured in person-years rather than Euros.

PHASE 2 (up to 5,000 videos): approx. 210 EUR one-time + 434 EUR/month
Here lies the single dominant decision: transition synthesis from Opus to Sonnet 5.5 once the citation pipeline (`search_result` blocks, verifier with attribution check against `scholar_id`) proves faithfulness stems from architecture rather than model scale. This halves 679 EUR down to 339 EUR. Concurrently drive response cache to 50%. Three VMs instead of one, as request latency, batch CPU, and database represent differing workload profiles. Monitoring on self-hosted GlitchTip. Still no dedicated vector database, no Qdrant, no Meilisearch — at 240,000 vectors that represents pure operational overhead and, worse, a secondary state that can diverge from review status.

PHASE 3 (up to 30,000 videos): approx. 1,190 EUR one-time + 2,060 EUR/month
Sonnet as default with Opus routing only for detected Ikhtilaf; cache hit rate to 75% via pre-caching the top 5,000 questions with a human approval step. Four VMs, audio-only, Bunny Volume CDN. 2,060 EUR/month is significant for a donor-supported project but achievable — and 82% is a single line item, synthesis, directly tied to user value. The entire infrastructure costs 156 EUR.

HOW TO RECOGNIZE THE PATH: Every phase maintains the same blueprint. One Postgres, one object store, audio over video, Batch API in ingest, prompt cache and response cache throughout, reranker as API instead of self-hosted, and a model interface with three roles so providers remain swappable. What changes across phases is not the architecture, but merely instance sizing and the synthesis model.

WHAT MONEY CANNOT BUY: Ingest for 4,000 h costs 1,190 EUR and is cheaper than a week of developer time. Human review of the same material requires 6,000–12,000 person-hours, or between 1.5 and 3 years with 20 active volunteers working 4 h/week. That is the true cost curve of this project, and it appears in no financial row above. Every architectural decision should be evaluated by whether it reduces this number — prioritize review by retrieval hits, translate segment-wise rather than freeform (halves effort per entry), populate Quran citations via lookup from canonical text rather than reviewer editing, and visibly flag unverified material instead of holding it back. A system that only functions with a 100% verified corpus will never launch.
