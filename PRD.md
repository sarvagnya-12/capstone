# Product Requirements Document — DryRunAI

**A GAN-Centric Generative AI Framework for Pre-Launch Product Simulation and Product–Market Fit Optimization**

## Provenance & Methodology

This PRD was reconstructed exclusively from five source documents provided by the project team (BMS College of Engineering, Dept. of ISE, AY 2025-26; team: Samanyu Gupta, Sarvagnya Akamanchi, Sejil Nooh Ansari, Shlok Naik Charan; guide: Dr. Shobha T):

| Document | Role |
|---|---|
| `t6.pdf` | Full Capstone Phase-1 report — the **certified, formally submitted** document. Highest authority. |
| `Synopsis capstone.pdf` | Early abstract/problem-definition + timeline. Subset of `t6.pdf`. |
| `syn1.docx (1)_removed.pdf` | Official Phase-1 synopsis approval form. Subset of `t6.pdf`. |
| `Lit_Review.pdf` | Working document: literature-review methodology + four architecture diagrams (Phase 1–3, plus a simplified pipeline view). **Not part of the certified report** — the team's most current internal design thinking, materially more technically specific than the SRS in `t6.pdf`, but not yet formally adopted. |
| `Lit_Review_Papers - Sheet1.pdf` | Spreadsheet of the 44 surveyed papers. Corroborates `t6.pdf` Ch.3–4. |

**Explicitly excluded from this PRD**, per instruction: the internal implementation of the dataset-extraction/collection pipeline at `Capstone Dataset/DryRunAI/` (catalog builder, asset manager, review builder, market service, product-intelligence service, knowledge-integration service, dataset-quality service). That pipeline is acknowledged only as the upstream **input source** for the core system described here. Its *interface* (output schemas, file formats, taxonomy) was separately reviewed to assess usefulness to the core system — see the addition to §21 and Open Decision #11 in §37 — but its internal code is still out of scope for requirements purposes.

**Tagging convention used throughout:** every non-trivial claim carries one of these tags —
- **[CONFIRMED — t6.pdf §x]** — stated in the certified report.
- **[DOCUMENTED DESIGN — Lit_Review.pdf]** — stated only in the working architecture diagrams.
- **[PROPOSED]** — presented in the SRS as one of several unresolved options (e.g., "React / Streamlit").
- **[INFERENCE]** — reasonably deduced from diagrams/structure but not explicitly stated.
- **[OPEN DECISION]** — genuinely unresolved or contradictory across sources; not resolved by this document.

Sections with no supporting material say so explicitly rather than inventing content.

---

## 1. Executive Summary

DryRunAI is a proposed **[CONFIRMED — t6.pdf Ch.1]** AI-driven, closed-loop simulation platform that lets organisations test a product concept — its visuals, packaging/branding variations, and a launch scenario (pricing, target demographic, messaging) — against **simulated customer personas** before committing to a real-world launch. It combines a **Generative Adversarial Network** for producing synthetic product-design variants with a **Large Language Model persona layer** for simulating audience reactions, wrapped in a feedback loop intended to iteratively refine which variant is recommended for launch. The system is explicitly positioned as a *decision-support/simulation engine*, not a generic content-generation tool **[CONFIRMED — Abstract, all three synopsis documents]**.

As of the source documents, DryRunAI is at the **design/Phase-1 report stage** of an academic capstone project — **no component is described as implemented**; the SRS, architecture diagrams, and literature survey constitute a design specification, not a status report on working software.

## 2. Problem Statement

**[CONFIRMED — t6.pdf Ch.2]** 70–80% of newly launched products fail within their first year due to poor market understanding and weak product-market alignment. Traditional pre-launch validation (surveys, focus groups, A/B testing, beta testing, social-media sentiment analysis) suffers from: limited audience reach, high operational cost, slow feedback cycles, human/moderator bias, inability to test multiple variations simultaneously, and — critically — most of these methods (A/B testing, beta testing) only surface problems **after** deployment. Existing generative-AI tools are oriented toward content generation, not decision simulation; no existing system combines GAN-based visual generation, LLM-based behavioural simulation, and feedback-driven optimisation into one pre-launch product-market-fit tool **[CONFIRMED — t6.pdf §2.1, §3.8 Research Gap Analysis]**.

## 3. Project Vision

To give organisations a "virtual testing environment" **[CONFIRMED — t6.pdf §1.6]** in which product concepts can be validated — visually, behaviourally, and strategically — before real-world investment, reducing launch uncertainty and financial risk through generative simulation rather than post-hoc analytics. The project's stated framing is that GANs should be understood as a **decision-support engine for strategic simulation**, not merely an image generator **[CONFIRMED — Abstract]**.

## 4. Goals

**[CONFIRMED — t6.pdf §1.3, §2.3, all synopsis documents]**
- Generate realistic, controlled synthetic product-design variations via GAN latent-space manipulation (colour, texture, layout, packaging/branding, presentation style).
- Simulate customer behaviour and reactions using LLM-based personas representing different demographics/behavioural patterns.
- Evaluate multiple launch scenarios (pricing, branding, target demographics, promotional messaging) in parallel.
- Detect product/launch risk and analyse sentiment before real-world deployment.
- Improve product designs iteratively via simulated feedback loops.
- Produce a ranked/recommended product variant with supporting analytics for launch decision-making.
- Provide a framework generalisable across industries (e-commerce, fashion, consumer goods, SaaS, marketing agencies, retail, start-ups) **[CONFIRMED — t6.pdf §1.4]**.

## 5. Non-Goals

**[INFERENCE, drawn from explicit scope/future-scope statements]**
- Not a guarantee of product success — **[CONFIRMED — t6.pdf Conclusion]**: "does not guarantee product success but helps organizations reduce uncertainty."
- Not, in the current documented scope, a system using real-time customer data, multilingual personas, regional consumer modelling, or enterprise-scale deployment — these are explicitly listed as **future** enhancements, i.e. out of current scope **[CONFIRMED — t6.pdf §1.4]**.
- Not a system that uses private or proprietary datasets — Legal Feasibility explicitly restricts it to public data **[CONFIRMED — t6.pdf §5.6]**.
- Not covering the dataset-acquisition/extraction pipeline (per this analysis's explicit scope boundary).

## 6. Target Users

**[CONFIRMED — t6.pdf §1.4 Scope, Fig 6.5 actor]** The platform's users are **organisations/businesses**, not end consumers. The use-case diagram labels the sole actor as "User (Business/Organization User)." Documented target industries/segments: e-commerce platforms, consumer goods companies, fashion brands, SaaS organisations, marketing agencies, retail businesses, start-ups. An `Admin` role also exists in the class diagram, responsible for managing users and monitoring simulations **[CONFIRMED — Fig 6.3]**.

No finer-grained role breakdown (e.g., "product manager" vs. "marketing lead" vs. "founder") is documented — the source material treats "the organisation" as a single actor type.

## 7. User Personas

*(Personas of the people who **use** DryRunAI — not to be confused with the AI-simulated **customer personas** the platform generates internally; see §15.)*

No narrative user personas (names, goals, pain points, day-in-the-life) are documented anywhere in the source material. What exists is the target-segment list in §6 and a single generic actor in the use-case diagram. Presenting invented personas (e.g., "Meet Priya, a product manager...") would fabricate detail not present in the documents, so this section is intentionally left at the level of the confirmed segment list rather than expanded. **[OPEN — no user-persona documentation exists; would need to be authored before UI/UX design work begins.]**

## 8. User Stories

**[INFERENCE — derived directly from the Use Case Diagram (Fig 6.5) and Functional Requirements table (5.2); phrasing is mine, content is not invented beyond what those two sources already specify.]**

- As an organisation user, I can register and securely log in, so that my product and simulation data is private to my account.
- As an organisation user, I can upload product images, descriptions, and branding details, so that the system has a concept to generate variants from.
- As an organisation user, I can configure a launch scenario (pricing strategy, target demographic, promotional messaging), so that simulations reflect a specific go-to-market plan.
- As an organisation user, I can trigger a simulation run, so that the system generates product variants and evaluates them against simulated personas.
- As an organisation user, I can view analytics (sentiment, risk, engagement, product-market-fit indicators) on a dashboard, so that I can compare variants.
- As an organisation user, I can download a report (PDF/CSV per Fig 6.5), so that findings can be shared outside the platform.
- As an organisation user, I receive a final recommended variant, so that I have a concrete launch decision to act on.
- As an admin, I can manage users and monitor simulations **[CONFIRMED — Fig 6.3 class diagram]**.

## 9. Functional Requirements

**[CONFIRMED — t6.pdf Table 5.2]**

| # | Module | Inputs | Function | Outputs |
|---|---|---|---|---|
| 1 | User Registration & Login | Credentials, org details | Authentication, validation, session mgmt | Secure session |
| 2 | Product Upload | Images, descriptions, branding | Validation, storage, preprocessing | Stored product data |
| 3 | Scenario Configuration | Pricing, demographics, launch scenario | Config setup, parameter mapping | Configured simulation environment |
| 4 | GAN-Based Product Generation | Product data, design inputs | GAN generates synthetic variations | Multiple product design variants |
| 5 | Persona Simulation | Product variants, predefined personas | LLM-based persona reasoning | Simulated customer feedback |
| 6 | Sentiment Analysis | Persona feedback text | NLP sentiment classification | Sentiment scores/labels (pos/neg/neutral) |
| 7 | Risk Detection | Sentiment + simulation results | Pattern/anomaly detection, rule-based + AI | Risk alerts/insights |
| 8 | Feedback Optimisation | Feedback + risk insights | "Reinforcement learning / feedback loop optimization" *(see §20 conflict)* | Refined product variations |
| 9 | Dashboard | Simulation outputs, analytics | Aggregation, visualization | Interactive dashboard/reports |
| 10 | Final Recommendation | Optimized variants, analytics | Ranking/scoring algorithms | Recommended product variant |

## 10. Non-Functional Requirements

**[CONFIRMED — t6.pdf Table 5.3]**

| Requirement | Target | Documented approach |
|---|---|---|
| Performance | Low latency/response time | GPU acceleration, optimized models, parallel processing |
| Scalability | Multiple concurrent users | Cloud infra (AWS/Azure), load balancing, microservices |
| Security | Encrypted, authenticated | SSL/TLS, JWT/OAuth, DB security |
| Reliability | Consistent output, low failure rate | Fault-tolerant design, redundancy, logging |
| Usability | Low learning curve | Intuitive UI/UX, guided workflows |
| Maintainability | Easy updates/fixes | Modular architecture, version control |
| Availability | ~99.9% uptime target | Cloud hosting, auto-scaling, backups |
| Portability | Cross-platform | Web-based, containerization (Docker) |

## 11. Core System Architecture

Two architectures exist in the source material at different levels of authority, and they should not be conflated:

**A. Certified 7-layer architecture [CONFIRMED — t6.pdf §6.1.1, Fig 6.1]:**
User Interface Layer → Application Layer → GAN Processing Layer → LLM Persona Layer → Optimisation Layer → Database Layer → Analytics Dashboard Layer.

**B. Working "Advanced End-to-End" architecture [DOCUMENTED DESIGN — Lit_Review.pdf, evolved across three labelled phases]:**
- *Phase 1* (conceptual): User Interface → AI Simulation Core (GANs + LLMs + Scenario Simulator + Market Reactions Simulation + Risk Analysis) → Evaluation Dashboard/Reports, fed by Data Sources (industry datasets, synthetic user data, trend data).
- *Phase 2* (component-level): adds a Data Preprocessing Module (image + text pipelines), a GAN Generation Module (StyleGAN/Stable Diffusion, latent sampling), an LLM Persona Simulation Module (GPT/LLaMA/Mistral, persona templates), an AI Agent Orchestration layer (LangChain/CrewAI: Persona Agents, Market Analyst Agent, Supervisor Agent, Risk Analysis Agent), a Design Optimization Engine (Bayesian/genetic algorithms), and an Analytics & Insight Engine — all behind a FastAPI/Flask API Orchestration Layer.
- *Phase 3* ("Advanced End-to-End System Architecture," the most detailed diagram): adds an API Gateway with Celery/Redis async task handling, a Vector Knowledge Base (FAISS/Weaviate) for product/persona/scenario embeddings, and a Model Ops & Infrastructure layer (Docker/Kubernetes model serving, MLflow/Weights & Biases experiment tracking).

**[OPEN DECISION #8]** These two architectures are not reconciled anywhere in the source material — the certified SRS never mentions vector databases, agent orchestration frameworks, Celery/Redis, or MLOps tooling, all of which appear only in the working document. Any implementation should treat architecture **B, Phase 3** as the team's current best thinking, but confirm it against the guide/examiners before treating it as settled scope, since it exceeds what was formally submitted.

## 12. System Components

**[CONFIRMED — t6.pdf §6.1.2, Fig 6.2]** Authentication, Product Upload, Scenario Configuration, GAN Generation, Persona Simulation, Sentiment Analysis, Risk Detection, Recommendation, Dashboard — each mapped 1:1 to the functional requirements in §9.

**[DOCUMENTED DESIGN — Lit_Review.pdf]** additionally names, at finer grain: a Data Preprocessing Module (CNN image embeddings, BERT/Sentence-Transformer text embeddings), a Prompt Engine and Model Registry (inside the API layer), a Supervisor Agent that "aggregates agent outputs, resolves conflicts, generates consensus insight," and a Design Optimization Engine distinct from the Feedback Optimisation functional requirement.

Class-level structure **[CONFIRMED — Fig 6.3]**: `User`, `Product`, `Simulation`, `Persona`, `Feedback`, `Recommendation`, `Admin`. Relationships: User uploads Product; Product is used in one-or-more Simulations; Simulation uses one-or-more Personas and generates multiple Feedback entries; Feedback is used to generate a Recommendation; Admin manages Users and monitors Simulations.

## 13. Data Flow

**[CONFIRMED — t6.pdf §1.6 seven-stage pipeline + Fig 6.4 Activity Diagram]**

1. **Product Input** — org uploads images, description, branding; may define target segments/launch scenarios.
2. **GAN-Based Product Generation** — GAN produces multiple synthetic design variants by varying attributes.
3. **Scenario Configuration** — pricing, branding style, target demographics, promotional messaging defined (per t6.pdf's stage numbering this is *after* generation; per the Activity Diagram, scenario selection happens *before* generation — see note below).
4. **LLM-Based Audience Simulation** — persona-based LLM reasoning generates reactions to the generated visuals.
5. **Sentiment & Risk Analysis** — responses classified (pos/neg/neutral); risks/misinterpretations flagged.
6. **Feedback-Driven Optimisation** — feedback used as a signal to refine subsequent GAN outputs.
7. **Final Recommendation** — variants compared/ranked; best variant recommended for launch.

**Ordering note [inconsistency, low-stakes]:** the prose stage list in t6.pdf §1.6 places Scenario Configuration as Stage 3 (after generation), while the Activity Diagram (Fig 6.4) sequences it as step 3 of 8 — *before* Product Generation (step 4) and Persona Simulation (step 5). Since a scenario (target demographic, pricing) plausibly needs to exist before persona simulation but not necessarily before visual generation, this is a minor internal inconsistency rather than a substantive conflict; the activity-diagram ordering (scenario before generation) is likely closer to the intended implementation order.

The loop-back arrow in the Activity Diagram returns from "Final Recommendation Generation" to "Scenario Selection" on a "More Iterations?" decision with **no documented stopping criteria** — see §20 and Open Decision #6.

## 14. AI/ML Components

| Component | Purpose | Input | Output | Named models/frameworks | Status |
|---|---|---|---|---|---|
| GAN | Generate synthetic product-design variants | Product image/description, latent vectors | N design variants | StyleGAN, StyleGAN2, DCGAN, Conditional GAN, CycleGAN, Pix2Pix, InfoGAN, BigGAN surveyed **[CONFIRMED — Ch.3]**; architecture diagrams select StyleGAN, and Phase 3 also lists **Stable Diffusion [DOCUMENTED DESIGN]** | Planned |
| LLM Persona Engine | Simulate customer reactions | Product variant + persona profile + scenario | Qualitative feedback, sentiment, purchase likelihood | "APIs / Open-source LLMs" **[PROPOSED — t6.pdf Table 5.5]**; GPT/LLaMA/Mistral **[DOCUMENTED DESIGN — Lit_Review.pdf]** | Planned |
| Multi-Agent Orchestration | Coordinate persona/market/risk agents, resolve conflicts | Agent outputs | Consensus insight | LangChain/CrewAI **[DOCUMENTED DESIGN only — absent from certified SRS]** | Proposed, not certified |
| Sentiment Analysis | Classify persona feedback | Feedback text | Positive/Negative/Neutral + score | "NLP-based sentiment classification" **[CONFIRMED — Table 5.2]**, no model named | Planned |
| Risk Detection | Flag launch risk | Sentiment + simulation results | Risk alerts | "Pattern detection, anomaly detection, rule-based + AI insights" **[CONFIRMED]**, no model named | Planned |
| Feedback/Optimisation Engine | Improve variants iteratively | Feedback, risk insights | Refined variants | Conflicting characterization — see §20/Open Decision #1 | Planned, mechanism undecided |
| Vector Knowledge Base | Semantic retrieval for persona/product context | Product/persona/scenario embeddings | Retrieved context for LLM prompts | FAISS/Weaviate, CNN + Sentence-Transformer embeddings **[DOCUMENTED DESIGN only]** | Proposed, not certified |

None of the above are described as trained, tested, or implemented in the source documents — all are design-stage.

## 15. Persona System

This is one of the least-resolved parts of the specification, and the ambiguity should be preserved rather than papered over.

- **Representation:** prompt-engineered profiles fed to an LLM. Concrete examples that appear anywhere in the material: "Price-sensitive student," "Urban professional," "Trend-driven buyer" **[DOCUMENTED DESIGN — Lit_Review.pdf Phase 2]**; and "Student," "Budget Shopper," "Premium User" **[DOCUMENTED DESIGN — Lit_Review.pdf simplified diagram]**. One example prompt structure is given: *"Persona: Price sensitive; Income: Low; Preference: affordability; Behavior: compares price first"* → qualitative opinion, purchase likelihood, sentiment.
- **Generation method:** **[CONFIRMED — t6.pdf §1.4 Scope]** "current implementation focuses on proof-of-concept development using public datasets and **predefined personas**." This directly implies a small, fixed/curated set, not a dynamically generated population.
- **Diversity/scale mechanism:** the literature survey cites relevant related work — *Population-Aligned Persona Generation* (population-level statistical modeling + LLM generation) and *Dynamic Persona Refinement Framework* (iterative persona updates via feedback loops) **[CONFIRMED — t6.pdf §3.3, Table 4.3 rows 14–15]** — but **no document states that DryRunAI itself implements either technique**. These are catalogued as prior art / research gaps, not confirmed system features.
- **How personas interact with products:** they "react" to the generated visual variant, producing qualitative feedback, sentiment, and purchase-likelihood signals **[CONFIRMED — t6.pdf §1.6 Stage 4]**.
- **Persona feedback → evaluation:** feeds Sentiment Analysis and Risk Detection modules (§9 #6–7), and in the working architecture, a Supervisor Agent aggregates multiple personas' outputs into a consensus insight **[DOCUMENTED DESIGN]**.

**[OPEN DECISION #3, CRITICAL]** How the system avoids being limited to a small, fixed list of personas — whether via a larger predefined library, population-sampling/statistical generation, or fully dynamic LLM-authored personas per simulation — is **not resolved** anywhere in the source material. This should be treated as a first-order design decision, not an implementation detail, since it materially affects whether "product-market fit" claims generalize beyond a handful of hand-picked example customers.

## 16. Product Generation System

- **What is generated:** synthetic product-design images/variants **[CONFIRMED — t6.pdf §1.6 Stage 2]**.
- **Attributes that can change:** listed inconsistently across sources — abstract/synopsis says *colour, texture, layout, presentation style*; t6.pdf Stage 2 says *colour, packaging style, layout, aesthetics, branding elements*. Treated here as overlapping, not contradictory, but the exact controllable attribute set is not formally fixed.
- **Attributes that must remain fixed:** not documented. No statement specifies which product properties (e.g., core product function, category, brand identity) are held constant during generation versus which are varied. **[OPEN]**
- **Variant count:** diagrams universally use a placeholder — "N product design variants" **[DOCUMENTED DESIGN]** — no target/typical/maximum count is documented anywhere.
- **Realism assessment:** no method specified. No FID/Inception Score, no human-evaluation protocol, no explicit "is this realistic enough" gate is documented, despite the literature survey itself repeatedly discussing GAN output-quality evaluation (e.g., DCG-GAN's "evaluation metrics to assess quality and novelty") as a feature of *surveyed* papers, not of DryRunAI itself. **[OPEN DECISION #5]**
- **Diversity assessment:** not documented — no metric for measuring variety across the N generated variants.
- **Connection to persona/market data:** variants are the object that personas react to (§15); scenario parameters (pricing, demographic, messaging) are configured alongside/around generation but the product-generation model itself is not documented as being conditioned on persona or market data at generation time — conditioning appears to happen only at the *evaluation* stage, not the *generation* stage. **[INFERENCE from the pipeline order in Fig 6.4]**

## 17. Market Simulation

This is the part of the system least developed relative to what the project's own subtitle ("Product–Market Fit Optimization") implies.

**What exists in the documents:**
- A Scenario Configuration module accepting pricing strategy, target demographic, and launch scenario as structured inputs **[CONFIRMED — t6.pdf §9 Functional Requirements #3]**.
- A "Market Reactions Simulation" box in the Phase-1 architecture diagram, and a "Market Analyst Agent" in the Phase 2/3 multi-agent layer **[DOCUMENTED DESIGN only]** — neither is elaborated with any modeling detail (no demand curve, no price-elasticity model, no competitor-behaviour logic).
- Outputs that use market language — "product-market fit score," "launch risk indicators," "market readiness insights" **[DOCUMENTED DESIGN]** — but these appear to be computed as **aggregates of persona-level sentiment/engagement/purchase-intent scores**, not as outputs of a distinct economic or agent-based market simulation.

**What is not present:** no documented mechanism for competitor modeling, dynamic pricing response, demand forecasting, or market-size estimation. "Market simulation," as actually specified, functions more as *scenario-conditioned persona aggregation* than as an independent market model. **[OPEN DECISION #7]** — Whether a genuine market-dynamics layer is intended (consistent with the project subtitle) or whether "product-market fit" is meant only as an aggregate persona metric is not resolved.

## 18. Marketing Strategy

**[CONFIRMED — t6.pdf §1.6 Stage 3, Table 5.2 #3]** Users configure: pricing strategy, target demographics, promotional/branding messaging, launch scenario. These are treated as simulation *parameters* (inputs that define a scenario to be evaluated) rather than as strategies the system generates or recommends autonomously. Scenario 2 ("Marketing Campaign Testing") and Scenario 3 ("Pricing Strategy Simulation") in §6.2.4 confirm multiple pricing tiers/ad creatives can be compared side-by-side, with simulated engagement/sentiment/purchase-intent per option.

## 19. Evaluation System

**[CONFIRMED — t6.pdf Table 5.2 #6–7]** Two dedicated modules: Sentiment Analysis (pos/neg/neutral classification of persona feedback) and Risk Detection (pattern/anomaly detection + rule-based + AI insights, producing risk alerts). **[DOCUMENTED DESIGN — Lit_Review.pdf Phase 3]** adds specific metric names not present in the certified SRS: sentiment score, engagement score, brand perception — feeding a "Feedback Optimization Loop / Evaluation Engine."

No ground-truth validation method is documented (i.e., nothing states how simulated persona sentiment is checked against real customer behaviour) — the entire evaluation loop is closed within the simulation itself. This is consistent with the project being a *pre-launch* simulation tool by design, but it is worth flagging that no documented mechanism exists for post-launch calibration of the simulated evaluators.

## 20. Optimization/Learning Loop

The documented feedback loop is: **Generate → Simulate (personas) → Evaluate (sentiment/risk) → Optimise → Generate again**, gated by a "More Iterations?" decision **[CONFIRMED — Fig 6.4]**.

**[OPEN DECISION #1, CRITICAL]** The *mechanism* of "Optimise" is characterized differently across every source that mentions it:
- Abstract / both synopsis documents: "latent space manipulation, hyperparameter tuning, scenario weighting, and threshold-based risk scoring" — no RL, no Bayesian/genetic optimization mentioned.
- t6.pdf Functional Requirements Table 5.2, row 8 ("Feedback Optimisation Module"): "Reinforcement learning / feedback loop optimization" — implying RL **is** the current mechanism.
- t6.pdf §1.4 Scope: explicitly lists "Reinforcement learning optimisation" under **Future enhancements** — implying RL is **not** current scope.
- Lit_Review.pdf Phase 2/3 diagrams: "Optimization Algorithms: Bayesian, Genetic" — no RL named in this box.
- Lit_Review.pdf simplified diagram: shows a "Reward Signals / RL Feedback Loop" box explicitly.

These cannot all be true simultaneously as a single confirmed design. **This document does not attempt to resolve which one is correct** — it must be decided before any optimisation code is written, since RL, Bayesian optimisation, and genetic algorithms imply materially different system designs (reward/environment modeling vs. surrogate-model-based search vs. population-based search).

**Stopping criteria [Open Decision #6]:** the Activity Diagram's "More Iterations?" branch has no documented rule (no score threshold, no max-iteration count, no convergence test).

**Human-in-the-loop:** no diagram or requirement documents a human approval step *inside* the loop — human involvement is only at the front (Stage 1: input) and back (viewing the dashboard / final recommendation). **[INFERENCE]** — full loop automation appears to be the intended design, but this is not explicitly asserted anywhere, only implied by the absence of a human-decision node in the activity diagram.

## 21. Training Requirements

Almost entirely undocumented. What exists:
- **[CONFIRMED — t6.pdf §5.4]** Minimum hardware: Intel i5/i7, 8GB RAM, 256GB SSD, "NVIDIA GPU recommended."
- **[CONFIRMED — t6.pdf §5.6 Legal Feasibility]** Only public datasets will be used (no private/proprietary data).
- **[CONFIRMED — t6.pdf §5.5]** GAN framework choice is either PyTorch or TensorFlow (unresolved either/or).

**Not documented anywhere:** whether the GAN (and, per Lit_Review.pdf, the diffusion model) is trained from scratch, fine-tuned from a pretrained checkpoint, or used purely at inference; what dataset size/composition training would require; retraining cadence; checkpointing strategy. **[OPEN DECISION #4, CRITICAL]**

**Internal tension worth flagging explicitly:** the literature survey itself repeatedly notes that the very models the architecture diagrams select — StyleGAN2 ("computational cost remains a challenge"), BigGAN ("demands extremely high computational resources") — are computationally heavy, yet the certified hardware requirement is a consumer-grade single machine with an unspecified GPU. No document reconciles this (e.g., by stating GANs will only run pretrained checkpoints at inference, or that training will happen on rented cloud GPU rather than the listed local hardware).

**Candidate training-data source, separately verified:** the dataset-extraction pipeline (`Capstone Dataset/DryRunAI/`, out of scope for this PRD otherwise) produces a real, deduplicated, validated product-image corpus via its Asset Manager service (`datasets/assets/catalog_v1/<product_id>/images/*.jpg`, tied to `image_metadata.csv`), plus real review text (`reviews.csv`) and brand/target-segment facts (`product_intelligence.csv`) that could ground GAN fine-tuning and LLM-persona grounding respectively. As of this review the pipeline is code-complete but has generated no real data yet (all record counts are 0 in its `project_manifest.json`) and is scoped entirely to footwear/sneakers — so it is a *plausible* training-data source for a footwear-vertical proof-of-concept, not a ready-made multi-industry dataset. See Open Decision #11.

## 22. Inference Requirements

**[DOCUMENTED DESIGN only — Lit_Review.pdf Phase 3 "Model Ops & Infrastructure"]** Model Serving via Docker containers, Kubernetes deployment, and a GPU inference server. This does not appear in the certified SRS at all — the SRS's software requirements table only lists "Cloud deployment tools (AWS/Azure/GCP)" generically **[PROPOSED — Table 5.5]**. No latency targets, no concurrency targets, and no batching strategy are documented for inference specifically (performance NFRs in §10 are stated at the whole-system level, not per-model).

## 23. Model Management

**[DOCUMENTED DESIGN only — Lit_Review.pdf Phase 3]** Experiment tracking via MLflow and Weights & Biases ("tracks model performance, simulation results, experiment runs"); a "Model Registry" is named as part of the API Orchestration Layer in Phase 2. None of this appears in the certified SRS. No versioning scheme, no rollback strategy, and no model-promotion process (dev → staging → prod) are documented anywhere.

## 24. User Workflow

**[CONFIRMED — Fig 6.4 Activity Diagram]** Login → Product Upload → Scenario Selection → Product Generation → Persona Simulation → Feedback Generation (incl. sentiment categorisation) → Risk Analysis → Final Recommendation Generation → (loop back to Scenario Selection if "More Iterations?" = Yes) → End.

**[CONFIRMED — Fig 6.5 Use Case Diagram]** From the user's perspective, the exposed actions are: Register, Login, Upload Product, Configure Scenarios, Run Simulation (which internally triggers GAN generation + persona simulation), View Analytics, Download Reports (PDF/CSV export named explicitly).

## 25. UI Requirements

Minimal documentation. **[CONFIRMED — t6.pdf Table 5.5]** Frontend is either React or Streamlit (unresolved). The Dashboard Module (§9 #9) must present "reports, charts and simulation insights." **[DOCUMENTED DESIGN — Lit_Review.pdf Phase 2/3]** names specific dashboard content: engagement heatmaps, persona sentiment charts, scenario comparisons, product-market-fit score, launch-risk indicators, design-variant ranking. Fig 1.6's marketing-style blueprint image additionally shows a "star rating" style variant comparison UI, but this is an illustrative concept graphic, not a wireframe/spec, and should not be treated as a UI requirement.

No user flows, wireframes, or accessibility requirements are documented. **[OPEN]**

## 26. Backend Requirements

**[PROPOSED — t6.pdf Table 5.5]** FastAPI or Flask (either/or, FastAPI noted as "preferred for performance"), Python as the core language, MySQL or MongoDB for storage (either/or). **[DOCUMENTED DESIGN — Lit_Review.pdf Phase 3]** adds specificity absent from the SRS: an API Gateway handling request validation, workflow orchestration, and model routing; Celery for async task queuing; Redis for caching; a Simulation Controller component. No API contract (endpoints, request/response schemas) is documented anywhere.

## 27. Storage Requirements

**[PROPOSED — t6.pdf Table 5.5]** MySQL or MongoDB, storing user data, product data, and simulation results (no schema documented). **[DOCUMENTED DESIGN only — Lit_Review.pdf Phase 3]** additionally specifies a Vector Knowledge Base (FAISS or Weaviate) storing product, persona, and scenario embeddings for semantic/persona search — entirely absent from the certified SRS. No data-retention policy, backup schedule, or storage-sizing estimate is documented.

## 28. Hardware Requirements

**[CONFIRMED — t6.pdf §5.4]** Processor: Intel i5/i7 or equivalent. RAM: minimum 8GB. Storage: minimum 256GB SSD. GPU: NVIDIA GPU "recommended" for GAN processing. Stated as "sufficient for both development and simulation processes" — see §21 for the unresolved tension between this spec and the compute demands of the literature-cited GAN models.

## 29. Security/Privacy Requirements

**[CONFIRMED — t6.pdf Table 5.3, §5.6]** SSL/TLS encryption; JWT/OAuth-based secure login; database-level security; user information and uploaded product data "should remain secure." Legal Feasibility confirms no private/proprietary datasets are used — only public data — which is as much a data-sourcing/IP constraint as a privacy one. No documented data-retention, deletion, or consent policy for uploaded product data; no mention of PII handling for any real customer data (moot for now, since personas are simulated, not real users — but relevant if "real-time customer data integration," listed as future scope, is ever added).

## 30. Testing Strategy

Not documented as a strategy. The only testing-related content is a calendar line item — "Testing, Debugging, Performance Evaluation & Optimization" (September, per both Gantt charts) **[CONFIRMED — Synopsis capstone.pdf, syn1.docx]**. No unit/integration/system test plan, no coverage target, no test-data strategy, and no acceptance-criteria checklist is documented. **[OPEN]**

## 31. Evaluation Metrics

**[CONFIRMED/DOCUMENTED DESIGN, mixed]** Sentiment score (pos/neg/neutral), risk alerts/indicators, engagement score, brand perception, product-market-fit score, launch-risk analysis — these are the metrics named across the SRS and architecture diagrams, all derived from aggregated persona/agent outputs. **Not documented:** any metric for generative-model output quality (no FID, Inception Score, or equivalent), any metric for persona-response consistency/reliability (despite this being flagged as a limitation of *surveyed* papers, e.g. Social Simulacra "may lack consistency across multiple simulation runs" — the survey's own critique of prior work is not addressed with a corresponding DryRunAI-side metric). **[OPEN DECISION #5]**

## 32. Research Methodology

**[CONFIRMED — t6.pdf Ch.3–4]** A 44-paper literature survey was conducted, split across five categories (GAN-based visual generation: 12 papers, LLM persona simulation: 12, AI agents: 12, application-oriented: 4, feedback optimisation: 4), with each of the four team members independently reviewing 11 papers spanning all categories **[CONFIRMED — Lit_Review.pdf "Literature Review Structure"]**. Findings were consolidated into a comparative summary table and a stated research-gap conclusion: no existing system unifies visual generation + persona simulation + agent interaction + feedback optimisation into one pre-launch product-market-fit tool.

**Not documented:** formal research hypotheses, a defined experimental design, baseline systems to benchmark against, ablation-study plans, or expected quantitative results. The "Research Gaps Identified" table in `Lit_Review.pdf` (one row per team member, per domain) is present as a structural placeholder but its Gaps column is **empty in the source document itself** — i.e., the team's own working document has not yet filled in this analysis. **[OPEN — genuinely unfinished in the source material, not merely undocumented for this PRD.]**

## 33. Success Criteria

Not quantified anywhere. The closest the documents come is a qualitative list of claimed advantages **[CONFIRMED — t6.pdf §1.6]**: reduced launch uncertainty, minimised financial losses, improved product-market-fit estimation, faster decision-making, scalable multi-scenario testing, reduced dependency on manual research. No target accuracy, adoption metric, or comparison-to-baseline threshold is defined. **[OPEN]**

## 34. Risks

**[INFERENCE, synthesised from tensions documented across the source material — not fabricated new risks]**
- **Compute/hardware mismatch** — certified hardware spec vs. the compute needs of the selected generative models (§21, §28).
- **Optimisation-mechanism ambiguity** — three incompatible descriptions of the feedback loop (§20) risk divergent implementation choices among team members.
- **Persona validity** — no ground-truth calibration mechanism; simulated personas' realism is asserted, not measured (§15, §19, §31).
- **Undefined stopping criteria** — the iterative loop could run indefinitely or terminate arbitrarily without a documented rule (§20).
- **Scope creep between architecture versions** — Lit_Review.pdf's Phase 3 architecture is considerably larger (vector DBs, multi-agent orchestration, MLOps stack) than what was certified in the SRS; building to Phase 3 without re-scoping/re-approval risks exceeding the academic timeline.
- **Public-dataset-only constraint** — may limit training-data realism/diversity for both the GAN and the persona system, given the Legal Feasibility restriction to public data.

## 35. Constraints

**[CONFIRMED]**
- No private or proprietary datasets — public data only (§5.6 Legal Feasibility).
- Academic timeline: February–October (2 Gantt charts confirm this window; t6.pdf implies submission within AY 2025-26).
- Team of 4 students, one faculty guide.
- Project framed and titled as **GAN-centric** — see Open Decision #2 for the tension this creates with the diffusion-model option appearing in the working architecture.
- Dataset-extraction pipeline is a separately maintained component (out of scope for this document, per the analysis brief).

## 36. Future Extensions

**[CONFIRMED — t6.pdf §1.4 Scope, §7.3 Future Scope]** Real-time customer data integration; multilingual persona simulations; regional consumer modelling; reinforcement-learning optimisation (explicitly future, not current — reinforcing Open Decision #1); enterprise-level deployment; Software-as-a-Service platform packaging; multi-domain simulations; international market testing.

## 37. Open Decisions

| # | Decision | Priority | Summary |
|---|---|---|---|
| 1 | Optimisation-loop mechanism (RL vs. Bayesian/genetic vs. heuristic weighting) | **CRITICAL** | Three incompatible characterizations across sources; §20 |
| 2 | "GAN-centric" branding vs. diffusion-model inclusion (Stable Diffusion in Phase 3) | **HIGH** | §14, §11 |
| 3 | Persona diversity/scale mechanism (fixed predefined set vs. dynamic/population-generated) | **CRITICAL** | §15 |
| 4 | Generative-model training strategy (from-scratch / fine-tune / inference-only) vs. stated hardware | **CRITICAL** | §21, §28 |
| 5 | Product-realism and persona-consistency evaluation methods (no FID/IS/reliability metric defined) | **HIGH** | §16, §19, §31 |
| 6 | Iterative-loop stopping criteria (undefined in Activity Diagram) | **HIGH** | §20 |
| 7 | Depth/nature of "market simulation" (aggregated persona metric vs. genuine market-dynamics model) | **MEDIUM** | §17 |
| 8 | Authority gap between certified SRS architecture and working Lit_Review.pdf architecture | **MEDIUM** | §11 |
| 9 | Pipeline-stage ordering: Scenario Configuration before or after GAN Generation (t6.pdf prose vs. Activity Diagram) | **LOW** | §13 |
| 10 | Literature review's own "Research Gaps Identified" table left unfilled per-member (Lit_Review.pdf) | **LOW** | §32 |
| 11 | No documented integration mechanics between the core system and the dataset-extraction pipeline's output (`master_products.csv`, images, reviews, market, product-intelligence) — no shared API, DB, or file-path convention specified anywhere in either codebase | **MEDIUM** | §21 |

None of these are resolved by this PRD, per the analysis instructions — they are flagged for explicit resolution by the project team/guide before the corresponding subsystem is implemented.
