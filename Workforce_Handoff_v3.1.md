**AI Workforce Handoff**

Master Orchestration Document

*Synthesis Edition --- Hardened, Checkpoint-Backed, Production-Ready*

*AI-Powered Automotive Inspection & Diagnostic Mobile App*

Version 3.1 · Final Build Specification

  ----------------------- -----------------------------------------------
  **Owner / Decision      Carl --- Workbay AI
  Maker**                 

  **Master Orchestrator** ZeptoClaw (hardened VPS + Telegram interface)

  **Primary LLMs**        Claude Sonnet 4.6 / Opus 4.7 · DeepSeek-V4-Pro
                          · GPT-5 fallback

  **Primary Workers**     Claude Code · Codex · Cursor

  **Specialty Builders**  Vapi · Lovable / v0 · FlutterFlow · Abacus

  **Failsafe System**     Checkpoint-based with full rollback (Section
                          XI)

  **Status**              Final spec --- ready for execution

  **Supersedes**          v1.0, v2.0, v3.0, v4.0

  **Date**                May 2026
  ----------------------- -----------------------------------------------

**How to use this document**

This is the master document for an AI agent-orchestrated software build,
designed to be read by two distinct audiences:

**Audience 1 --- Carl (decision maker).** Section I for the mission,
Section II to understand the workforce, Section IX (Orchestration
Playbook) to direct ZeptoClaw, Section XI (Checkpoint System) to
understand the failsafe, and Section XII (Prompt Library) for the exact
text to send your orchestrator. The technical sections (IV--VII) are
reference material; ZeptoClaw will memorize them.

**Audience 2 --- ZeptoClaw (master orchestrator).** Load this entire
document into project memory on day one. It is your source of truth.
Sections III--VIII are the product specification. Sections IX--XVI
govern your behavior. Sections X (SOPs), XI (Checkpoints), and XII
(Prompt Library) define standard workflows. Section XVI (Security
Hardening) is non-negotiable.

  -----------------------------------------------------------------------
  *Onboarding prompt on day one: \"/onboard --- You are now my Chief of
  Staff for the Automotive Inspection AI project. Read this handoff
  document v3.1 in full. Confirm by giving me a one-page summary of
  Sections I, II, IX, XI, and XIII. Then ask me up to 10 clarifying
  questions before we begin Sprint 0. Log every answer as a decision
  entry.\"*

  -----------------------------------------------------------------------

**What changed from v3.0 and why**

Three significant upgrades from v3.0, and rejection of two changes
proposed in v4.0:

  -------------------------------------------------------------------------
  **Change**         **Direction**    **Why**
  ------------------ ---------------- -------------------------------------
  OpenClaw →         Adopted from     OpenClaw had CVE-2026-25253 (CVSS
  ZeptoClaw          v4.0             8.8) plus the ClawHavoc supply chain
                                      incident. ZeptoClaw is the
                                      security-hardened sibling, written in
                                      Rust with container isolation, secret
                                      encryption at rest, and prompt
                                      injection detection. Drop-in
                                      replacement with zeptoclaw migrate.

  Add                Adopted from     Released April 2026, 1M context,
  DeepSeek-V4-Pro    v4.0             \~8-9x cheaper than Opus 4.7 on
  for research and                    output. Routed for vendor
  cost-sensitive LLM                  evaluations, long-document analysis,
  work                                and high-volume non-critical paths.
                                      Claude remains primary for the voice
                                      agent.

  Structured         Adopted from     Cleaner than free-form WhatsApp.
  Telegram commands  v4.0             Reduces ambiguity in orchestrator
  (/dispatch,                         dispatch.
  /research, etc.)                    

  VPS sizing: 2GB →  Rejected v4.0    v4.0\'s 2GB / 1 vCPU droplet cannot
  8GB for            sizing           run orchestrator + FastAPI + LiveKit
  orchestrator,                       agent concurrently. Right-sized at
  separate 16GB for                   \$48 + \$96/month.
  backend                             

  Audio retained for Restored from    v4.0 deleted audio immediately. This
  90 days with       v3.0             forecloses the strategic capability
  opt-in training                     of learning from accumulated shop
  flag                                data. Restored.

  Checkpoint-based   NEW              Section XI. Every decision and
  failsafe system                     milestone produces a snapshot. Any
                                      change is reversible to a known-good
                                      state.

  Security hardening NEW              Section XVI. v4.0\'s setup guide ran
  playbook                            everything as root --- directly
                                      undermined the threat model ZeptoClaw
                                      exists to defend against. This
                                      version hardens properly.
  -------------------------------------------------------------------------

**Table of contents**

I. Mission briefing 4

II\. The AI workforce 5

III\. Product vision & MVP scope 8

IV\. Technical architecture 10

V. AI pipeline specification 13

VI\. Data model & storage 16

VII\. Mobile, backend, dashboard specs 18

VIII\. Build roadmap (agent-run scaled) 21

IX\. Orchestration playbook 25

X. Standard operating procedures 28

XI\. Checkpoint & failsafe system 32

XII\. Prompt library 37

XIII\. Pre-authorized decisions 40

XIV\. Decision log template 41

XV\. Risks & mitigations 43

XVI\. Security hardening playbook 45

XVII\. Security, privacy & compliance 49

XVIII\. Timeline & budget 51

Appendix A: Hardened Day 1 setup 53

Appendix B: Tool URLs 57

Appendix C: Example inspection flow 58

Appendix D: Technology evaluation rationale 59

Appendix E: Glossary 62

**I. Mission briefing**

Build and ship a cloud-hosted AI-powered automotive inspection app. A
technician completes a full vehicle inspection hands-free, guided by a
voice agent over a Bluetooth headset. Voice captures findings, photos
document them, the system extracts measurements and conditions, and a
complete report lands on the service advisor\'s web dashboard within 30
seconds of session end.

MVP supports English and Spanish, handles 30 concurrent voice sessions,
serves 50 shops at launch. The build is executed by an AI agent
workforce orchestrated by ZeptoClaw on a hardened DigitalOcean VPS,
accessed by Carl through Telegram from anywhere. Every meaningful change
is checkpointed and reversible.

**Single owner**

Carl. All product, scope, budget, and trade-off decisions escalate to
him.

**Single orchestrator**

ZeptoClaw. All execution dispatch flows through it. Carl does not talk
directly to specialist workers unless explicitly intervening (Cursor for
visual debug, Vapi UI for voice prompt iteration).

**Why this build can be solo-orchestrated in 2026**

-   Voice agent frameworks (LiveKit Agents) collapsed five microservices
    into a single supervised pipeline.

-   Coding agents (Claude Code, Codex) reliably ship production-quality
    code from clear specifications.

-   Meta-orchestrators (ZeptoClaw) supervise coding agents from a phone,
    freeing the owner from sitting at a terminal.

-   Long-context cost-efficient LLMs (DeepSeek-V4-Pro) make research and
    analysis affordable at scale.

-   Checkpoint-based failsafes (Section XI) make every decision
    reversible.

This document is the rigorous specification that makes the above work.
Without a clear spec the agents thrash. With this loaded into
ZeptoClaw\'s project memory, the build executes.

**Success criteria**

-   A technician completes a full inspection hands-free in a real shop
    environment.

-   Findings, photos, and measurements are correctly associated with
    checklist items in 95%+ of sessions.

-   Advisor receives a complete report within 30 seconds of session end.

-   Voice pipeline median latency under 500ms, p95 under 800ms.

-   English and Spanish operational at launch.

-   System handles 30 concurrent voice sessions at MVP launch.

-   Zero unrecoverable incidents during build: every regression rolls
    back to a verified checkpoint.

-   Total build cost under \$45,000 all-in.

**II. The AI workforce**

**Org chart**

Three layers: decision maker (Carl), orchestrator (ZeptoClaw +
DelegateTool sub-agents), specialist workers.

+-----------------------------------------------------------------------+
| Carl (decision maker)                                                 |
|                                                                       |
| │ Telegram (primary) + WhatsApp (fallback)                            |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ZeptoClaw (Chief of Staff, hardened DigitalOcean VPS)                 |
|                                                                       |
| │ 4-6MB Rust binary; container-isolated; Argon2id-encrypted secrets   |
|                                                                       |
| │ 9 channels supported; DelegateTool for parallel fan-out             |
|                                                                       |
| │                                                                     |
|                                                                       |
| ├──▶ Claude Code → primary backend & voice agent (Python)             |
|                                                                       |
| ├──▶ Codex → async parallel tasks, overnight PRs                      |
|                                                                       |
| ├──▶ Cursor → visual code review, debugging intervention              |
|                                                                       |
| ├──▶ DeepSeek-V4-Pro → research, long-doc analysis, cost-sensitive    |
| paths                                                                 |
|                                                                       |
| ├──▶ Claude Sonnet 4.6/Opus 4.7 → voice agent reasoning (production   |
| runtime)                                                              |
|                                                                       |
| ├──▶ DelegateTool sub-agents → parallel multi-vendor evaluations      |
|                                                                       |
| ├──▶ Vapi → voice flow prototyping (Carl direct)                      |
|                                                                       |
| ├──▶ Lovable / v0 → dashboard mockups & production UI                 |
|                                                                       |
| ├──▶ FlutterFlow → mobile app scaffolding                             |
|                                                                       |
| └──▶ Abacus AppLLM → rapid full-app prototypes                        |
+-----------------------------------------------------------------------+

**Role assignments**

  --------------------------------------------------------------------------
  **Component**        **Primary Agent**   **Secondary**      **Cost Tier**
  -------------------- ------------------- ------------------ --------------
  LiveKit voice agent  Claude Code         Cursor for bugs    Standard
  (Python)                                                    

  FastAPI backend      Claude Code         Codex for stubs    Standard

  Postgres schema &    Claude Code         ---                Standard
  migrations                                                  

  Auth0 integration    Codex               Claude Code review Standard

  Stripe billing       Codex               Claude Code review Standard

  Flutter mobile app   FlutterFlow +       Cursor for native  Standard
                       Claude Code                            

  Next.js dashboard    Lovable             Claude Code wiring Standard

  Voice prompt design  Vapi (Carl direct)  ZeptoClaw drafts   Low

  Vendor evaluations   DeepSeek-V4-Pro     Carl final pick    Low

  Long-document        DeepSeek-V4-Pro (1M ---                Low
  analysis             context)                               

  Production voice     Claude Sonnet 4.6   Opus 4.7           Premium
  reasoning                                escalation         

  Test data generation DeepSeek-V4-Flash   Codex              Very low

  CI/CD pipelines      Claude Code         ---                Standard

  Documentation        ZeptoClaw (memory   Carl review        Low
  auto-gen             dump)                                  
  --------------------------------------------------------------------------

**Why this LLM split**

Claude Sonnet 4.6 stays primary for the voice agent because production
voice reasoning has tight latency requirements and Anthropic\'s tool-use
reliability matters when tools are firing on every conversational turn.
Opus 4.7 handles complex follow-up reasoning and report generation.
DeepSeek-V4-Pro handles everything Carl-facing that doesn\'t require
sub-500ms latency: vendor research, document analysis, test data,
long-context investigations. The cost difference is significant ---
DeepSeek-V4-Pro at \$1.74/\$3.48 per million input/output tokens vs.
Opus 4.7\'s much higher pricing --- and for non-realtime work that gap
matters.

**Operating principles**

-   **Single source of truth:** This document. Every agent reads it
    before acting.

-   **Spec before code:** Every dispatch references a specific section.

-   **Checkpoint before risk:** Every decision and milestone produces a
    snapshot per Section XI.

-   **Time-box everything:** Every run has an estimate and a hard cap at
    2x.

-   **Decisions are append-only:** Every product or technical decision
    lands in the decision log linked to a checkpoint.

-   **Cost transparency:** Daily cost report. Vendor spend over \$25/day
    requires Carl approval.

-   **Recommendations attached to decisions:** When ZeptoClaw escalates,
    it includes its own recommendation and rationale.

-   **Reversibility by default:** If an action cannot be reversed via
    checkpoint rollback, it requires explicit Carl sign-off.

**Escalation rules**

**Always escalate to Carl:**

-   Any user-facing change (UI text, voice prompts, brand)

-   Security-relevant changes (auth, encryption, PII handling)

-   Billing changes (Stripe, pricing, refunds)

-   New external dependencies or vendor accounts

-   Production deploys

-   Vendor spend over \$25/day or one-time over \$100

-   Architectural changes from this document

-   New features not in the roadmap

-   Any irreversible action (data deletion, key rotation that breaks
    active sessions)

-   Any task exceeding 2x its time estimate

**Never escalate (handle autonomously, log to checkpoint):**

-   Code style, formatting, variable naming

-   Adding logging, tests, or documentation

-   Bug fixes within an existing component

-   Dependency minor and patch updates

-   Retry strategies, timeouts, rate limit configs

-   Choosing between technically equivalent libraries

-   Checkpoint creation (routine)

**Communication protocol**

Channel: Telegram (primary), WhatsApp (fallback). Both supported by
ZeptoClaw\'s channel system.

Cadence:

-   07:00 ET --- daily briefing

-   09:00 -- 18:00 ET --- active dispatch window; 5-minute response SLA

-   12:30 ET --- midday cost and run-rate check

-   18:00 ET --- end-of-day report and checkpoint creation

-   02:00 ET --- automatic daily full-state checkpoint

-   Friday evening --- weekly review and decision log audit

**III. Product vision & MVP scope**

**Vision**

Replace paper checklists and unstructured technician notes with an
intelligent voice-guided inspection assistant. Hands-free, voice-first,
multilingual. Captures findings, photos, and measurements during the
inspection itself, and auto-generates a complete digital report for the
service advisor --- eliminating the gap between what a technician saw
and what the customer hears about.

**Strategic direction**

-   Integrates with shop management systems, parts catalogs, and labor
    time guides (post-MVP)

-   Learns from accumulated shop data to predict component failures

-   Continuously improves through fleet-wide telemetry

-   Serves as data foundation for AI-driven repair operations

**Target users**

**Automotive technician (primary)**

-   Noisy service bay, greasy hands, Bluetooth headset, speaks naturally

-   English or Spanish depending on shop demographics

**Service advisor (secondary)**

-   Web dashboard at service counter, reviews completed inspections

**Shop administrator (tertiary)**

-   Manages technicians, billing, subscription

**MVP scope: in**

-   Hands-free voice-guided inspection (English + Spanish)

-   Photo capture linked to inspection items

-   Measurement and condition extraction from speech

-   Adaptive follow-up questions (rule-based + LLM-driven)

-   Auto-generated report in web dashboard within 30 seconds of session
    end

-   Shop-level subscription billing via Stripe

-   Admin: invite/disable technicians, view billing

-   Anonymized audio retention with opt-in training flag (default off)

**MVP scope: out**

-   Customer-facing report links, SMS, or email notifications

-   Parts catalog or labor time lookups

-   VIN decoder integration (manual Y/M/M entry for MVP)

-   Computer vision on uploaded photos (photos stored only)

-   Shop management system integrations

-   Multi-shop chain views

-   Native iOS or Android codebases (Flutter only)

**IV. Technical architecture**

**Architecture philosophy**

Two-VPS topology: orchestrator separated from production workload for
blast-radius isolation. Modular monolith on the backend. Unified voice
pipeline orchestrated by LiveKit Agents. Single Postgres + JSONB +
pgvector for flexibility. DigitalOcean for predictable pricing and
managed services. Every component checkpointable per Section XI.

**Stack selection**

  -----------------------------------------------------------------------
  **Layer**                  **Selection**
  -------------------------- --------------------------------------------
  Mobile                     Flutter + livekit_client + auth0_flutter

  Voice transport            LiveKit Cloud

  Voice orchestration        LiveKit Agents (Python) on dedicated VPS

  STT primary                AssemblyAI Universal-3 Pro Streaming

  STT backup                 Deepgram Nova-3

  LLM (voice agent,          Claude Sonnet 4.6 primary, Opus 4.7
  realtime)                  escalation, GPT-5 fallback

  LLM (research, async)      DeepSeek-V4-Pro (1M context, cost-efficient)

  LLM (high-volume routine)  DeepSeek-V4-Flash

  TTS                        ElevenLabs

  Orchestrator               ZeptoClaw on hardened DigitalOcean VPS

  Backend                    Python + FastAPI on separate DigitalOcean
                             VPS

  Database                   PostgreSQL 16 + JSONB + pgvector
                             (DigitalOcean Managed DB, HA tier)

  Object storage             DigitalOcean Spaces (S3-compatible)

  Checkpoint storage         DigitalOcean Spaces (separate bucket,
                             versioned, lifecycle-managed)

  Web dashboard              Next.js 15 on Vercel

  Authentication             Auth0

  Payments                   Stripe

  Cloud                      DigitalOcean (NYC3 primary region)

  Observability              Datadog (logs, metrics, traces)

  CI/CD                      GitHub Actions (deploy pipeline only ---
                             ZeptoClaw is the orchestrator)

  Backup automation          DigitalOcean Snapshots + custom pg_dump to
                             Spaces
  -----------------------------------------------------------------------

**Infrastructure sizing (verified, not undersized)**

  ------------------------------------------------------------------------------
  **Component**      **Spec**           **Cost/month**    **Reason**
  ------------------ ------------------ ----------------- ----------------------
  Orchestrator VPS   8GB RAM, 4 vCPU,   \$48              ZeptoClaw +
                     160GB SSD                            DelegateTool
                                                          sub-agents + buffer

  Backend VPS        16GB RAM, 8 vCPU,  \$96              FastAPI + LiveKit
                     320GB SSD                            Agent worker + 30
                                                          concurrent voice
                                                          sessions

  Managed Postgres   4GB RAM, 2 vCPU,   \$60              Production tier with
                     60GB, HA                             standby; pgvector
                                                          ready

  Spaces (data +     500GB allocation   \$10-25           Photos, audio,
  checkpoints)                                            checkpoint manifests

  LiveKit Cloud      Pay-per-minute     \$50-200          Variable; free tier
                                                          covers initial dev

  Total infra        ---                \$264-429/month   Stable, sized for 30
  (launch)                                                concurrent sessions
  ------------------------------------------------------------------------------

Compare to v4.0\'s claim of \$32/month for infra: that figure is for an
undersized single-VPS topology that cannot handle the stated MVP load.
v3.1 sizing is honest.

**System topology**

+-----------------------------------------------------------------------+
| Carl\'s phone                                                         |
|                                                                       |
| │ Telegram (primary)                                                  |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| ZeptoClaw VPS --- 8GB / 4 vCPU                                        |
|                                                                       |
| \- Hardened Ubuntu 24.04 LTS                                          |
|                                                                       |
| \- Non-root user, UFW, fail2ban, SSH key-only                         |
|                                                                       |
| \- ZeptoClaw systemd service                                          |
|                                                                       |
| \- Container isolation per agent execution                            |
|                                                                       |
| \- Encrypted secrets store (XChaCha20-Poly1305 + Argon2id)            |
|                                                                       |
| │ HTTPS to backend; orchestrates remote agents                        |
|                                                                       |
| ▼                                                                     |
|                                                                       |
| Backend VPS --- 16GB / 8 vCPU                                         |
|                                                                       |
| \- FastAPI (api, agent, worker apps)                                  |
|                                                                       |
| \- LiveKit Agent worker (Python)                                      |
|                                                                       |
| \- Same hardening profile                                             |
|                                                                       |
| │                                                                     |
|                                                                       |
| ┌─┼──────────────────────┐                                            |
|                                                                       |
| ▼ ▼ ▼                                                                 |
|                                                                       |
| Managed Postgres Spaces                                               |
|                                                                       |
| \- HA tier - data bucket                                              |
|                                                                       |
| \- daily auto-snap - checkpoints bucket                               |
|                                                                       |
| \- pgvector - versioned, lifecycle-managed                            |
|                                                                       |
| \- off-site replication                                               |
|                                                                       |
| External: LiveKit Cloud · AssemblyAI · Anthropic · DeepSeek ·         |
| ElevenLabs                                                            |
|                                                                       |
| External: Auth0 · Stripe · Vercel · Datadog · GitHub                  |
|                                                                       |
| Dashboard (Next.js / Vercel) --- accesses Backend VPS over HTTPS      |
+-----------------------------------------------------------------------+

**V. AI pipeline specification**

**Voice loop**

Each conversational turn is a single loop managed by LiveKit Agents:

1\. Audio in (Flutter → LiveKit Cloud → Agent via WebRTC)

2\. STT streaming (AssemblyAI with automotive key terms loaded)

3\. Endpointing (LiveKit semantic VAD)

4\. LLM invocation (Claude Sonnet 4.6 default, Opus 4.7 for complex,
GPT-5 fallback)

5\. Tool calls (backend APIs)

6\. TTS streaming (ElevenLabs, starts on first LLM tokens)

7\. Audio out (Agent → LiveKit → Flutter)

**Target latency:** \<500ms median, \<800ms p95, measured from user
end-of-speech to first agent audio.

**LLM routing strategy**

  ------------------------------------------------------------------------
  **Path**               **Model**             **Why**
  ---------------------- --------------------- ---------------------------
  Voice agent turns      Claude Sonnet 4.6     Tool-use reliability +
  (production realtime)                        latency

  Complex follow-up /    Claude Opus 4.7       Reasoning quality
  report generation                            

  Voice fallback (Claude GPT-5 via LiveKit     Multi-provider resilience
  outage)                router                

  Vendor research /      DeepSeek-V4-Pro       1M context, \~8-9x cheaper
  comparison                                   

  Long-document analysis DeepSeek-V4-Pro       Full repo fits in context

  High-volume routine    DeepSeek-V4-Flash     \$0.14/\$0.28 per M tokens
  tasks                                        

  Code generation        Claude Code (Sonnet   Coding agent benchmarks
  (coding agent backend) 4.6)                  
  ------------------------------------------------------------------------

**STT configuration**

Provider: AssemblyAI Universal-3 Pro Streaming. Why: \~150ms P50
latency, lowest WER, turn-by-turn domain term injection up to 1,000
terms.

**Automotive term injection**

-   Master vocabulary in Postgres (parts, systems, tools, measurements)

-   Pre-load relevant subset at session start based on vehicle and
    checklist category

-   Reload turn-by-turn as context shifts

-   Examples: caliper, rotor, OBD2, control arm, tie rod end, MAF
    sensor, CV axle

**Multilingual**

-   English and Spanish at launch, native AssemblyAI models for each

-   Language selection per technician profile

-   Separate term lists per language

**Tool definitions**

+-----------------------------------------------------------------------+
| get_checklist(vehicle_id)                                             |
|                                                                       |
| get_current_item(session_id)                                          |
|                                                                       |
| save_finding(session_id, item_id, finding)                            |
|                                                                       |
| attach_media(session_id, item_id, media_url)                          |
|                                                                       |
| request_photo(session_id, item_id, reason)                            |
|                                                                       |
| advance_checklist(session_id)                                         |
|                                                                       |
| mark_complete(session_id)                                             |
|                                                                       |
| lookup_term(query) \-- Phase 1.5 (RAG)                                |
|                                                                       |
| create_checkpoint(reason) \-- session-level checkpoint                |
+-----------------------------------------------------------------------+

**TTS configuration**

Provider: ElevenLabs. Streaming starts on first LLM tokens. 1-2 default
voices per language, configurable per technician in Phase 2.

**NLU split**

**Fast path (no LLM call)**

-   Commands: next, skip, repeat, pause, go back

-   Measurement regex: digits + units

-   Bound to current inspection item via session state

**LLM path**

-   Free-form observations

-   Adaptive follow-ups

-   Disambiguation

**Computer vision (Phase 2 --- schema only in MVP)**

Photos stored raw in MVP. Schema includes forward-compatible ai_analysis
block:

+-----------------------------------------------------------------------+
| {                                                                     |
|                                                                       |
| \"media_id\": \"uuid\",                                               |
|                                                                       |
| \"session_id\": \"uuid\",                                             |
|                                                                       |
| \"item_id\": \"string\",                                              |
|                                                                       |
| \"uploaded_at\": \"timestamp\",                                       |
|                                                                       |
| \"media_type\": \"photo \| video \| audio\",                          |
|                                                                       |
| \"s3_key\": \"string\",                                               |
|                                                                       |
| \"ai_analysis\": {                                                    |
|                                                                       |
| \"status\": \"pending \| processing \| complete \| skipped\",         |
|                                                                       |
| \"detected_parts\": \[\],                                             |
|                                                                       |
| \"anomalies\": \[\],                                                  |
|                                                                       |
| \"measurements\": {},                                                 |
|                                                                       |
| \"confidence_scores\": {},                                            |
|                                                                       |
| \"analyzed_at\": \"timestamp \| null\",                               |
|                                                                       |
| \"model_version\": \"string \| null\"                                 |
|                                                                       |
| }                                                                     |
|                                                                       |
| }                                                                     |
+-----------------------------------------------------------------------+

**VI. Data model & storage**

**Core tables**

**shops**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| name text                                                             |
|                                                                       |
| subscription_status enum (trial, active, past_due, canceled)          |
|                                                                       |
| stripe_customer_id text                                               |
|                                                                       |
| created_at timestamp                                                  |
|                                                                       |
| updated_at timestamp                                                  |
+-----------------------------------------------------------------------+

**users**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| shop_id uuid FK → shops                                               |
|                                                                       |
| auth0_id text unique                                                  |
|                                                                       |
| role enum (technician, advisor, admin)                                |
|                                                                       |
| name text                                                             |
|                                                                       |
| preferred_language text default \'en\'                                |
|                                                                       |
| active boolean                                                        |
|                                                                       |
| audio_training_opt_in boolean default false                           |
|                                                                       |
| created_at timestamp                                                  |
|                                                                       |
| updated_at timestamp                                                  |
+-----------------------------------------------------------------------+

**vehicles**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| shop_id uuid FK                                                       |
|                                                                       |
| vin text encrypted                                                    |
|                                                                       |
| year int                                                              |
|                                                                       |
| make text                                                             |
|                                                                       |
| model text                                                            |
|                                                                       |
| mileage int                                                           |
|                                                                       |
| created_at timestamp                                                  |
+-----------------------------------------------------------------------+

**inspection_sessions**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| shop_id uuid FK                                                       |
|                                                                       |
| technician_id uuid FK                                                 |
|                                                                       |
| vehicle_id uuid FK                                                    |
|                                                                       |
| checklist_template_id uuid FK                                         |
|                                                                       |
| customer_concern text                                                 |
|                                                                       |
| status enum (in_progress, completed, abandoned)                       |
|                                                                       |
| started_at timestamp                                                  |
|                                                                       |
| completed_at timestamp                                                |
|                                                                       |
| session_audio_s3_key text                                             |
|                                                                       |
| audio_retention_until timestamp \-- 90 days default, indefinite if    |
| opt-in                                                                |
+-----------------------------------------------------------------------+

**findings**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| session_id uuid FK                                                    |
|                                                                       |
| checklist_item_id text                                                |
|                                                                       |
| transcript text                                                       |
|                                                                       |
| structured_data jsonb \-- measurements, ratings, follow-up answers    |
|                                                                       |
| condition enum (good, fair, poor, na)                                 |
|                                                                       |
| created_at timestamp                                                  |
+-----------------------------------------------------------------------+

**media**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| session_id uuid FK                                                    |
|                                                                       |
| finding_id uuid FK nullable                                           |
|                                                                       |
| media_type enum (photo, video, audio)                                 |
|                                                                       |
| s3_key text                                                           |
|                                                                       |
| ai_analysis jsonb \-- Phase 2 population                              |
|                                                                       |
| created_at timestamp                                                  |
+-----------------------------------------------------------------------+

**checklist_templates**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| name text                                                             |
|                                                                       |
| vehicle_filter jsonb                                                  |
|                                                                       |
| version int                                                           |
|                                                                       |
| items jsonb                                                           |
|                                                                       |
| created_at timestamp                                                  |
|                                                                       |
| updated_at timestamp                                                  |
+-----------------------------------------------------------------------+

**checkpoints**

+-----------------------------------------------------------------------+
| id uuid PK                                                            |
|                                                                       |
| checkpoint_id text unique \-- e.g., CP-0042                           |
|                                                                       |
| type enum (sprint, deploy, decision, daily, manual)                   |
|                                                                       |
| created_at timestamp                                                  |
|                                                                       |
| git_tag text                                                          |
|                                                                       |
| db_snapshot_id text                                                   |
|                                                                       |
| spaces_manifest_key text                                              |
|                                                                       |
| zeptoclaw_memory_key text                                             |
|                                                                       |
| metrics_snapshot jsonb                                                |
|                                                                       |
| decision_log_delta jsonb                                              |
|                                                                       |
| sha256_manifest text                                                  |
|                                                                       |
| notes text                                                            |
|                                                                       |
| created_by enum (zeptoclaw, chad)                                     |
+-----------------------------------------------------------------------+

**Encryption & retention**

-   VINs encrypted at rest with DigitalOcean encryption keys +
    application-layer envelope encryption

-   Auth0 holds credentials; we never store passwords

-   Session audio: 90 days hot retention default; indefinite if
    technician opts in

-   Media: hot 30 days → Spaces IA tier 1 year → cold storage

-   Checkpoints: sprint and decision checkpoints retained indefinitely;
    daily checkpoints retained 90 days

**VII. Mobile, backend, dashboard specs**

**Mobile app (Flutter)**

**Platform targets**

-   iOS 16+ (iPhone 12 or newer)

-   Android 12+ (mid-tier or better)

-   Rugged tablets supported but not required

**Key modules**

-   flutter_webrtc + livekit_client (audio routing)

-   camera package (photo and short video)

-   Riverpod or Bloc (state, survives backgrounding)

-   Hive or Isar (offline queue for findings + media)

-   auth0_flutter (auth)

-   Material 3 (high contrast, large tap targets, voice-first)

**Connectivity behavior**

-   Online: full real-time voice pipeline

-   Degraded: banner shown, checklist visible, voice pauses

-   Offline: checklist navigable from cache; findings + media queued;
    auto-sync on reconnect

**Offline sync conflict resolution**

-   client_generation_id on every write (monotonic per device)

-   SHA-256 content hash for deduplication

-   Server-side last-write-wins by timestamp, with conflict log for
    manual review

**Backend (FastAPI)**

**Service layout (modular monolith)**

+-----------------------------------------------------------------------+
| backend/                                                              |
|                                                                       |
| ├── apps/                                                             |
|                                                                       |
| │ ├── api/ \# FastAPI REST + WSS                                      |
|                                                                       |
| │ ├── agent/ \# LiveKit Agent worker                                  |
|                                                                       |
| │ └── worker/ \# Background jobs (reports, S3 cleanup, checkpoint     |
| creation)                                                             |
|                                                                       |
| ├── domain/                                                           |
|                                                                       |
| │ ├── sessions/                                                       |
|                                                                       |
| │ ├── findings/                                                       |
|                                                                       |
| │ ├── checklists/                                                     |
|                                                                       |
| │ ├── reports/                                                        |
|                                                                       |
| │ ├── users/                                                          |
|                                                                       |
| │ ├── billing/                                                        |
|                                                                       |
| │ └── checkpoints/ \# Section XI failsafe system                      |
|                                                                       |
| ├── infra/                                                            |
|                                                                       |
| │ ├── db/ \# SQLAlchemy + Alembic                                     |
|                                                                       |
| │ ├── storage/ \# Spaces client (S3-compatible)                       |
|                                                                       |
| │ ├── ai/ \# AssemblyAI, Claude, DeepSeek, ElevenLabs                 |
|                                                                       |
| │ └── auth/ \# Auth0                                                  |
|                                                                       |
| └── tests/                                                            |
+-----------------------------------------------------------------------+

**Key endpoints**

-   POST /sessions --- start inspection

-   GET /sessions/:id --- fetch state

-   POST /sessions/:id/complete --- close session, trigger report

-   WSS /sessions/:id/stream --- real-time updates

-   POST /sessions/:id/findings --- create finding (agent tool)

-   PATCH /findings/:id --- update finding

-   POST /media/upload-url --- pre-signed Spaces URL

-   POST /media/:id/attach --- link media to finding

-   GET /checklists?make=&model=&year= --- fetch checklist

-   GET /sessions/:id/report --- fetch report

-   POST /webhooks/stripe --- Stripe events

-   POST /checkpoints --- create (admin/zeptoclaw)

-   POST /checkpoints/:id/restore --- rollback (admin only, MFA)

**Dashboard (Next.js)**

**Stack**

-   Next.js 15 (App Router)

-   React 19

-   Tailwind + shadcn/ui

-   Vercel hosting

-   Auth0 SDK

**MVP screens**

-   Login + shop selection

-   Inspection queue (live-updating)

-   Inspection detail (per item: transcript, photos, measurements,
    condition)

-   Report print or PDF export

-   Admin: users, billing, subscription

-   Admin: checkpoint browser (read-only listing of recent checkpoints
    with restore button gated by MFA)

**VIII. Build roadmap (agent-run scaled)**

Agent run: single ZeptoClaw-orchestrated execution unit, 30 min to 4
hours. Each sprint produces verified checkpoints; failure rolls back to
last green.

**Sprint 0: Foundation (target: 18 runs)**

  ---------------------------------------------------------------------------------------
  **Run**   **Task**                                   **Primary**      **Checkpoint?**
  --------- ------------------------------------------ ---------------- -----------------
  0.1       Provision both VPSes per Section XVI       Manual + Claude  CP-0001
            hardening                                  Code             

  0.2       Install ZeptoClaw with full hardening      Manual +         CP-0002
            profile                                    ZeptoClaw        
                                                       onboarding       

  0.3       Load handoff doc v3.1 into ZeptoClaw       ZeptoClaw        CP-0003
            project memory                                              

  0.4       Provision Managed Postgres (HA tier)       Claude Code      CP-0004

  0.5       Provision Spaces (data + checkpoints       Claude Code      ---
            buckets)                                                    

  0.6       Auth0 tenant + integration test            Codex            ---

  0.7       LiveKit Cloud + agent worker skeleton on   Claude Code      CP-0005
            Backend VPS                                                 

  0.8       Flutter app skeleton + auth + camera       FlutterFlow +    CP-0006
            permissions                                Claude Code      

  0.9       GitHub repo + CI/CD pipeline (deploy-only) Claude Code      ---

  0.10      Datadog observability wired in             Claude Code      ---

  0.11      Stripe sandbox + webhook stub              Codex            ---

  0.12      Implement checkpoint system per Section XI Claude Code      CP-0007

  0.13      Vapi voice prototype for brake inspection  Carl direct      ---

  0.14      Tech tests Vapi prototype in shop          Carl in person   ---

  0.15      Iterate voice flow on tech feedback        Vapi (Carl)      ---

  0.16      ZeptoClaw self-documentation skill         ZeptoClaw        ---

  0.17      Risk register + circuit breaker thresholds ZeptoClaw        ---
            loaded                                                      

  0.18      Sprint 0 retro + checkpoint                ZeptoClaw        CP-0008
  ---------------------------------------------------------------------------------------

**Sprint 1: Core inspection loop (target: 40 runs)**

Three parallel tracks. Each track produces an intermediate checkpoint at
completion. ZeptoClaw coordinates and gates merges.

**Track A --- Backend & Voice Agent (18 runs)**

-   Static checklist seeding (master template)

-   Inspection session lifecycle (start, progress, complete) --- API

-   Findings persistence with structured_data JSON

-   Media upload flow (pre-signed Spaces URLs)

-   Report builder (JSON + HTML render)

-   LiveKit agent: AssemblyAI STT integration

-   LiveKit agent: Claude tool definitions and routing

-   LiveKit agent: ElevenLabs TTS streaming

-   Voice tools wired to backend

-   Domain term injection from Postgres vocab

-   Fast-path command handling (next/skip/repeat)

-   Measurement regex extraction

-   Adaptive follow-up routing

-   End-to-end smoke test with synthetic audio

-   End-to-end smoke test in quiet room

-   End-to-end smoke test in noisy shop bay

-   Cost monitoring + circuit breaker

-   Track A merge --- CP-1.A

**Track B --- Mobile App (12 runs)**

-   Vehicle entry screen

-   VIN scan via camera (manual fallback)

-   Session start (calls backend, joins LiveKit room)

-   Checklist progress view

-   Finding cards (live display)

-   Photo capture flow

-   Bluetooth headset detection and routing

-   Offline queue for findings + media

-   Reconnect logic

-   Auth0 login flow

-   Mobile UX polish

-   Track B merge --- CP-1.B

**Track C --- Dashboard (10 runs)**

-   Login + shop selection

-   Inspection queue (live-updating)

-   Inspection detail view

-   Per-item drill-down

-   Report print stylesheet

-   PDF export

-   Admin: technician management

-   Admin: billing view

-   Admin: checkpoint browser (read-only with restore CTA behind MFA)

-   Track C merge --- CP-1.C

Sprint 1 final checkpoint: CP-1.FINAL --- end-to-end voice inspection
working, report renders, system load-tested at 10 concurrent.

**Sprint 2: Polish & launch prep (target: 22 runs)**

-   Spanish language support (STT, LLM prompt, TTS voice, mobile i18n)

-   Stripe production keys + billing screens

-   Security hardening pass (rate limits, KMS rotation, pen test prep)

-   Load test (target: 30 concurrent voice sessions)

-   Pilot with 2-3 friendly shops

-   Pilot feedback iteration

-   UX polish pass

-   iOS App Store submission (contractor-assisted)

-   Android Play Store submission

-   Operational runbooks

-   External security audit

-   Sprint 2 final checkpoint: CP-2.FINAL

**Sprint 3: Limited GA (target: 15 runs)**

-   Onboarding flow for first paying shops

-   Self-service signup

-   Documentation site

-   Support email + ticketing

-   On-call rotation

-   First 10-20 paying shops onboarded

-   Phase 2 backlog grooming

-   Sprint 3 / GA checkpoint: CP-GA

**IX. Orchestration playbook**

**ZeptoClaw\'s day**

+-----------------------------------------------------------------------+
| 07:00 ET Daily briefing → Carl\'s Telegram                            |
|                                                                       |
| (overnight summary, today\'s plan, blockers, cost yesterday)          |
|                                                                       |
| 09:00 ET Active dispatch begins                                       |
|                                                                       |
| Respond to Carl within 5 minutes                                      |
|                                                                       |
| Run scheduled tasks                                                   |
|                                                                       |
| Monitor in-flight agents                                              |
|                                                                       |
| DelegateTool spawns parallel sub-agents as needed                     |
|                                                                       |
| 12:30 ET Midday check-in                                              |
|                                                                       |
| (cost report, run status, surprises, circuit breaker state)           |
|                                                                       |
| 17:00 ET Final escalations of the day                                 |
|                                                                       |
| (anything needing Carl before EOD)                                    |
|                                                                       |
| 18:00 ET End-of-day report                                            |
|                                                                       |
| (work done, work in flight, tomorrow\'s plan)                         |
|                                                                       |
| Trigger end-of-day checkpoint if material progress made               |
|                                                                       |
| Overnight Codex jobs run (in container isolation)                     |
|                                                                       |
| DeepSeek-V4-Pro research runs                                         |
|                                                                       |
| Auto-tests on main branch                                             |
|                                                                       |
| Daily snapshot at 02:00 ET (CP-DAILY-YYYYMMDD)                        |
|                                                                       |
| S3 lifecycle, log rotation                                            |
|                                                                       |
| Vendor cost reconciliation                                            |
+-----------------------------------------------------------------------+

**Dispatch patterns**

**Pattern A --- Build a new feature**

1\. Identify spec section in this document.

2\. Identify primary agent from role matrix.

3\. Verify last checkpoint is green; create pre-feature checkpoint if
needed.

4\. Draft prompt: goal, spec reference, acceptance criteria, time
estimate.

5\. Dispatch into container-isolated execution.

6\. Monitor; relay clarifying questions to Carl.

7\. On completion, run acceptance check (tests pass, smoke test green).

8\. Log decision; merge to main; create post-feature checkpoint.

**Pattern B --- Fix a bug**

1\. Reproduce the bug (or capture repro from Carl).

2\. Identify owning component.

3\. Dispatch primary agent with: bug description, repro steps, expected
vs. actual.

4\. On fix, request regression test.

5\. Update decision log if approach changed.

**Pattern C --- Run an investigation**

1\. Frame as DeepSeek-V4-Pro job (1M context, cost-efficient).

2\. For multi-vendor comparisons, use DelegateTool to spawn parallel
sub-agents.

3\. Define: question, inputs, expected output format, success criteria,
time budget.

4\. Dispatch and disconnect.

5\. On return, summarize for Carl with recommendation.

**Pattern D --- Surface a decision**

1\. List options (max 3).

2\. State trade-offs in 1-2 sentences each.

3\. Note ZeptoClaw\'s recommendation.

4\. Send via Telegram.

5\. On Carl\'s response, log decision linked to current checkpoint, then
proceed.

**Pattern E --- Rollback (new in v3.1)**

Triggered automatically by circuit breaker, manually by Carl, or by
ZeptoClaw when a task fails recoverably.

1\. Identify target checkpoint.

2\. Compute rollback delta (what will change).

3\. Present to Carl with explicit confirmation required.

4\. On confirmation, execute per SOP-09.

5\. Log rollback as a new decision entry.

**Tooling rules**

-   Always quote dollar costs before incurring (\>\$5/day vendor spend)

-   Always check this doc for existing direction before asking Carl

-   Always include a recommendation when escalating

-   Always create a checkpoint before any production change

-   Never approve security-relevant changes without Carl sign-off

-   Never deploy to production without Carl sign-off

-   Never delete data without a checkpoint preserving it

-   Always run agent code inside container isolation

**X. Standard operating procedures**

**SOP-01: Add a new inspection checklist item**

1\. Create pre-change checkpoint.

2\. Define item: id, label, category, expected measurements, follow-ups.

3\. Dispatch Claude Code to update seed data and migration.

4\. Dispatch Codex to write tests.

5\. Update domain term list if new vocabulary.

6\. Test one Vapi session.

7\. Commit, deploy to staging.

8\. Log decision; create post-change checkpoint.

**SOP-02: Vendor evaluation**

1\. DeepSeek-V4-Pro job: research 3-5 candidates against criteria.

2\. For parallel speedup, use ZeptoClaw DelegateTool to spawn sub-agents
per vendor.

3\. Produce comparison matrix with pricing, capabilities, risks.

4\. ZeptoClaw summarizes for Carl (1 page).

5\. Carl decides via Telegram.

6\. Log decision with full rationale and linked research artifact.

**SOP-03: Deploy to staging**

1\. CI passes on main.

2\. Create pre-deploy checkpoint.

3\. Run smoke tests in CI.

4\. Push to staging via GitHub Actions.

5\. Run end-to-end test.

6\. If clean: ask Carl about production. If not: revert via rollback to
pre-deploy checkpoint.

**SOP-04: Deploy to production**

1\. Staging green for 24 hours.

2\. Carl approves via Telegram (\`/deploy prod \--tag vX.Y.Z\`).

3\. Create pre-deploy production checkpoint (CP-DEPLOY-vX.Y.Z).

4\. Tag release.

5\. Blue-green deploy.

6\. Watch error rate and latency for 30 minutes.

7\. If circuit breaker fires: auto-rollback to CP-DEPLOY-vX.Y.Z
(previous).

8\. Notify Carl of outcome.

**SOP-05: Daily briefing format**

+-----------------------------------------------------------------------+
| 📋 Daily Briefing --- \[Date\]                                        |
|                                                                       |
| 🟢 Overnight progress                                                 |
|                                                                       |
| \- \[Run X.Y\]: \[outcome\]                                           |
|                                                                       |
| \- Daily checkpoint: \[CP-DAILY-YYYYMMDD\]                            |
|                                                                       |
| \- \[Codex/DeepSeek job\]: \[result\]                                 |
|                                                                       |
| 🔴 Blockers                                                           |
|                                                                       |
| \- \[None / list\]                                                    |
|                                                                       |
| ❓ Decisions needed today                                             |
|                                                                       |
| \- \[None / Q1 / Q2 / Q3\]                                            |
|                                                                       |
| 🎯 Today\'s plan                                                      |
|                                                                       |
| \- \[Run X.A\]: \[task\]                                              |
|                                                                       |
| \- \[Run X.B\]: \[task\]                                              |
|                                                                       |
| 📊 Metrics (vs last green checkpoint)                                 |
|                                                                       |
| \- Voice latency p95: XXXms (last green: XXXms)                       |
|                                                                       |
| \- Error rate: X% (last green: X%)                                    |
|                                                                       |
| \- Cost yesterday: \$XX (last green: \$XX)                            |
|                                                                       |
| 💰 Cost: yesterday \$XX \| week \$XXX \| budget \$X,XXX               |
+-----------------------------------------------------------------------+

**SOP-06: End-of-day report format**

+-----------------------------------------------------------------------+
| 📋 EOD --- \[Date\]                                                   |
|                                                                       |
| ✅ Completed                                                          |
|                                                                       |
| \- \[Run X.Y\]: \[outcome + key decisions\]                           |
|                                                                       |
| \- Decisions logged: \[D-NNN, D-MMM\]                                 |
|                                                                       |
| \- Checkpoint created: \[CP-NNN\]                                     |
|                                                                       |
| 🔄 In flight (overnight)                                              |
|                                                                       |
| \- \[Codex job\]: \[expected complete by\]                            |
|                                                                       |
| \- \[DeepSeek job\]: \[expected complete by\]                         |
|                                                                       |
| 🌅 Tomorrow\'s priorities                                             |
|                                                                       |
| \- \[Run X.Z\]: \[task\]                                              |
|                                                                       |
| 📝 Decisions logged today: \[count, IDs\]                             |
|                                                                       |
| 💾 Checkpoints created today: \[list\]                                |
|                                                                       |
| 💰 Today\'s spend: \$XX \| WTD: \$XXX                                 |
+-----------------------------------------------------------------------+

**SOP-07: Cost alert**

Triggered when daily spend exceeds \$25 or weekly exceeds \$200.

1\. Immediate Telegram to Carl: vendor, amount, what triggered it.

2\. Recommended action: pause job, cap, or proceed.

3\. Carl responds; ZeptoClaw executes.

**SOP-08: Agent run stuck**

Trigger: agent run hits 2x its time estimate.

1\. ZeptoClaw pauses the run.

2\. Captures current state, error, attempted approaches.

3\. Three options to Carl: extend, switch agents, escalate to Cursor for
human debug.

4\. Default if no Carl response within 1 hour: extend by 50% once, then
hard stop with no rollback.

**SOP-09: Checkpoint creation**

Triggered automatically per Section XI rules, or manually via
\`/checkpoint create\`.

1\. Verify last test suite passed.

2\. Tag git commit (e.g., checkpoint-CP-0042).

3\. Trigger Postgres logical backup → Spaces.

4\. Snapshot Managed DB via DigitalOcean API.

5\. Export ZeptoClaw memory state to encrypted file.

6\. Export decision log delta since last checkpoint.

7\. Capture metrics snapshot.

8\. Generate SHA-256 manifest of all artifacts.

9\. Upload to checkpoints bucket with versioning.

10\. Log CP-NNN entry to decision log; notify Carl of checkpoint ID.

**SOP-10: Rollback to checkpoint**

1\. Carl initiates: \`/rollback to CP-NNN\`.

2\. ZeptoClaw verifies checkpoint exists and SHA-256 manifest validates.

3\. Computes rollback delta --- diff of code, schema, config between
current state and CP-NNN.

4\. Displays to Carl: \"This will revert X files, Y DB changes, Z config
changes. Estimated downtime: N minutes.\"

5\. Carl must confirm by typing the exact checkpoint ID.

6\. ZeptoClaw enters maintenance mode (pauses all agents).

7\. Restore git to tag.

8\. Restore DB from snapshot (point-in-time if needed).

9\. Restore config and secrets references.

10\. Restore ZeptoClaw memory.

11\. Run smoke tests.

12\. If green: exit maintenance mode, log rollback event, create new
checkpoint CP-RB-NNN.

13\. If red: alert Carl, recommend Cursor intervention.

**SOP-11: Decision rollback (subset)**

When you want to reverse a specific vendor or config decision without
rolling back all code.

1\. Identify decision ID (e.g., D-0023: chose AssemblyAI for STT).

2\. Verify the system supports the decision swap via config (this is an
architecture requirement: vendor swaps are config flags).

3\. Update config flag.

4\. Restart affected service.

5\. Validate.

6\. Log new decision D-MMM superseding D-0023.

**SOP-12: Circuit breaker trip**

Automatic, triggered by metric thresholds.

1\. ZeptoClaw monitors continuously.

2\. Thresholds (configurable):

-   Voice latency p95 \> 1500ms for 5 minutes → alert + recommend
    rollback

-   Error rate \> 5% for 2 minutes → alert + recommend rollback

-   API cost \> \$50/day → alert (no auto-rollback)

-   Failed transcriptions \> 10% → alert

-   Voice agent worker memory \> 90% → alert + scale

3\. On trip: page Carl, propose rollback to last green checkpoint.

4\. Carl confirms or overrides.

**SOP-13: Daily checkpoint at 02:00 ET**

Automatic, every day.

Captures full state --- git, DB, config, metrics. Retained 90 days.

Used as the baseline for circuit breaker comparisons throughout the next
day.

**XI. Checkpoint & failsafe system**

  -----------------------------------------------------------------------
  *This is the failsafe layer Carl asked for. Every meaningful change
  produces a checkpoint. Every checkpoint can be restored. The build
  cannot go sideways without a way back.*

  -----------------------------------------------------------------------

**Purpose**

Provide a verifiable, time-stamped, content-hashed snapshot of the
entire project state at every decision point. Enable full rollback to
any prior checkpoint, partial rollback of individual decisions, and
automatic rollback when circuit breakers trip. No change is irreversible
unless explicitly flagged so by Carl.

**What a checkpoint contains**

  -----------------------------------------------------------------------
  **Component**          **Captured As**
  ---------------------- ------------------------------------------------
  Code state             Git tag on main branch (e.g.,
                         checkpoint-CP-0042)

  Database state         Postgres logical backup (pg_dump) + DigitalOcean
                         snapshot ID + pgvector index

  Object storage state   Spaces bucket manifest with object versions and
                         SHA-256 hashes

  Configuration state    All env vars, feature flags, secrets references
                         (not values, only ARNs/keys)

  Orchestrator state     ZeptoClaw memory dump (encrypted) + decision log
                         up to checkpoint

  Vendor state           List of configured vendors, API key
                         fingerprints, webhook URLs

  Metrics state          Voice latency p50/p95, error rates, cost
                         run-rate at checkpoint moment

  Decision state         All decisions logged since previous checkpoint
                         (delta)

  Test state             Last passing test suite report + coverage

  Infrastructure state   DigitalOcean VPS snapshot IDs (both VPSes)

  Manifest               SHA-256 of every artifact in the checkpoint,
                         signed
  -----------------------------------------------------------------------

**Checkpoint types**

  -------------------------------------------------------------------------
  **Type**            **Trigger**                       **Retention**
  ------------------- --------------------------------- -------------------
  CP-SPRINT-N         End of each sprint                Forever

  CP-DECISION-N       Before any decision marked        Forever
                      irreversible                      

  CP-DEPLOY-vX.Y.Z    Before each production deploy     Forever (linked to
                                                        release tag)

  CP-DAILY-YYYYMMDD   Automatic 02:00 ET                90 days

  CP-MANUAL-N         Carl-requested via /checkpoint    Forever
                      create                            

  CP-AUTO-N           ZeptoClaw discretionary (before   30 days
                      risky run)                        

  CP-RB-N             Created automatically after a     Forever
                      successful rollback               
  -------------------------------------------------------------------------

**Checkpoint storage**

-   Primary: DigitalOcean Spaces (checkpoints bucket), versioned

-   Cross-region replication: weekly sync to a second DigitalOcean
    region for disaster recovery

-   Encryption: server-side AES-256 at rest, plus client-side envelope
    encryption for orchestrator memory dumps

-   Access control: read by ZeptoClaw and admin role only; restore
    requires MFA

-   Cost: estimated \$5-20/month for full project history

**Decision-linked checkpoints**

Every decision logged per Section XIV references a checkpoint. The
pattern is: state before decision (linked checkpoint) → decision made →
state after decision (new checkpoint). This means at any point you can:

-   See exactly what the system looked like when the decision was made

-   Roll back to that state if the decision was wrong

-   Replay subsequent decisions from a known-good base

-   Audit decisions against the metrics that justified them at the time

**Rollback options**

**Full rollback (SOP-10)**

Revert the entire system to a prior checkpoint. Used for catastrophic
regressions or when multiple changes need reverting together. Estimated
downtime: 5-15 minutes depending on DB size.

**Decision rollback (SOP-11)**

Reverse a single decision via config flag without rolling back code.
Used for vendor swaps, threshold adjustments, or feature toggles. No
downtime.

**Forward repair**

Sometimes rolling back loses too much progress. Alternative: keep
current state, apply targeted fix, create new checkpoint. The decision
log records the bug and the fix. ZeptoClaw recommends this when rollback
would lose \>2 days of work.

**Branch-and-fix**

For complex regressions, create a branch from the last green checkpoint,
apply fixes there, validate, then merge forward. Slower but safer than
direct repair on broken main.

**Circuit breakers (SOP-12)**

Automated rollback triggers. ZeptoClaw continuously monitors. If a
threshold is exceeded, ZeptoClaw alerts Carl and recommends rollback.
Carl\'s response triggers the rollback or override.

  -------------------------------------------------------------------------
  **Metric**             **Threshold**   **Window**    **Auto-rollback?**
  ---------------------- --------------- ------------- --------------------
  Voice latency p95      \>1500ms        5 min         Recommend; Carl
                                                       confirms

  Error rate             \>5%            2 min         Recommend; Carl
                                                       confirms

  Failed transcriptions  \>10%           10 min        Recommend; Carl
                                                       confirms

  API cost               \>\$50/day      1 day         Alert only

  Voice agent worker     \>90%           5 min         Alert + auto-scale
  memory                                               

  Backend 5xx rate       \>2%            5 min         Recommend; Carl
                                                       confirms
  -------------------------------------------------------------------------

**What hard data each checkpoint preserves**

Per Carl\'s requirement: \"hard data points to return to during the
build if anything goes sideways.\" Each checkpoint includes:

-   Performance metrics: voice latency p50/p95, end-to-end session time,
    tool-call latency

-   Quality metrics: WER on sampled audio, missed-finding rate, photo
    association accuracy

-   Cost metrics: \$/inspection, \$/voice-minute, vendor breakdown

-   Reliability metrics: uptime, error rates, retry rates

-   Test results: full suite pass/fail, coverage, regression baseline

-   Configuration: vendor selection, model versions, feature flags,
    thresholds

-   Decisions: every D-NNN logged since previous checkpoint

-   Sample audio: 10 random session recordings for QA comparison

-   Sample sessions: 5 full inspection sessions with transcript +
    photos + report

**Recovery objectives**

-   RPO (Recovery Point Objective): max 24 hours data loss (daily
    checkpoint cadence)

-   RTO (Recovery Time Objective): full rollback in under 30 minutes for
    catastrophic events

-   MTTD (Mean Time To Detect): under 5 minutes via Datadog + ZeptoClaw
    monitoring

-   MTTR (Mean Time To Recover): under 1 hour for routine regressions

**Verification rituals**

Checkpoints are useless if they can\'t actually restore. ZeptoClaw runs
verification rituals:

-   Weekly: restore most recent CP-DAILY to a staging environment, run
    smoke tests, destroy

-   Monthly: full DR drill --- simulate primary VPS loss, restore from
    checkpoint to a new VPS

-   Before each sprint checkpoint: validate manifest SHA-256s match
    artifacts

-   On checkpoint creation failure: alert Carl immediately; never
    silently fail

**XII. Prompt library**

Exact prompts Carl uses to direct ZeptoClaw. Copy-paste from this
section into Telegram. ZeptoClaw recognizes both slash commands and
free-form natural language.

**Day 1 --- Onboarding ZeptoClaw**

  -----------------------------------------------------------------------
  */onboard --- You are now my Chief of Staff for the Automotive
  Inspection AI project. Read this handoff document v3.1 in full and load
  it into your project memory. Configure DelegateTool, channel allowlist,
  and container isolation per Section II. Give me a one-page summary of
  Sections I, II, IX, XI, XIII. Then ask me up to 10 clarifying questions
  before we begin Sprint 0. Log every answer as a decision entry linked
  to CP-0003.*

  -----------------------------------------------------------------------

**Daily --- Morning briefing**

  -----------------------------------------------------------------------
  */daily --- Give me the daily briefing per SOP-05.*

  -----------------------------------------------------------------------

**Dispatch --- Build a feature**

  -----------------------------------------------------------------------
  */dispatch \"Build \[feature\]. Spec section \[X\]. Primary agent:
  \[Claude Code / Codex\]. Estimate: \[N hours\]. Create pre-feature
  checkpoint.\"*

  -----------------------------------------------------------------------

**Dispatch --- Run a feature directly**

  -----------------------------------------------------------------------
  */dispatch run \[X.Y\] --- Use best judgment on prompt construction.
  Report back on completion or question.*

  -----------------------------------------------------------------------

**Decision --- Respond to a question**

  -----------------------------------------------------------------------
  *Re your question about \[topic\]: \[decision\]. Log it linked to
  current checkpoint and proceed.*

  -----------------------------------------------------------------------

**Research --- Send DeepSeek-V4-Pro**

  -----------------------------------------------------------------------
  */research \"\[question\]. Output format: \[comparison matrix / report
  / recommendation\]. Time budget: \[hours\]. Use DelegateTool for
  parallel evaluation if multi-vendor.\"*

  -----------------------------------------------------------------------

**Async --- Queue Codex overnight**

  -----------------------------------------------------------------------
  */queue codex \"\[task\]. Acceptance criteria: \[list\]. Spec
  reference: \[Section\]. Open PR when ready and notify at 07:00.\"*

  -----------------------------------------------------------------------

**Cost --- Run rate check**

  -----------------------------------------------------------------------
  */cost report \--detail --- Today, this week, this month. Top 3 line
  items. Any unusual trends?*

  -----------------------------------------------------------------------

**Pause --- Stop everything**

  -----------------------------------------------------------------------
  */pause \--reason \"\[reason\]\" --- Pause all in-flight runs. Send
  current state of each. Resume when I say.*

  -----------------------------------------------------------------------

**Resume**

  -----------------------------------------------------------------------
  */resume --- Resume all paused work.*

  -----------------------------------------------------------------------

**Status --- See running agents**

  -----------------------------------------------------------------------
  */status --- Show all in-flight agent runs, their estimates, elapsed
  time, and current step.*

  -----------------------------------------------------------------------

**Checkpoint --- Create on demand**

  -----------------------------------------------------------------------
  */checkpoint create \"\[reason\]\" --- Create a manual checkpoint per
  SOP-09.*

  -----------------------------------------------------------------------

**Checkpoint --- List recent**

  -----------------------------------------------------------------------
  */checkpoint list \--last 10 --- Show last 10 checkpoints with type,
  timestamp, and key metrics.*

  -----------------------------------------------------------------------

**Checkpoint --- Show details**

  -----------------------------------------------------------------------
  */checkpoint show CP-NNN --- Show full manifest, decisions captured,
  and metrics snapshot.*

  -----------------------------------------------------------------------

**Rollback --- Full**

  -----------------------------------------------------------------------
  */rollback to CP-NNN --- Per SOP-10. Show me the rollback delta, then
  I\'ll confirm by typing the exact checkpoint ID.*

  -----------------------------------------------------------------------

**Rollback --- Decision only**

  -----------------------------------------------------------------------
  */rollback decision D-NNN --- Per SOP-11. Reverse just this decision
  via config; do not roll back code.*

  -----------------------------------------------------------------------

**Deploy --- Staging**

  -----------------------------------------------------------------------
  */deploy staging \--tag vX.Y.Z --- Per SOP-03.*

  -----------------------------------------------------------------------

**Deploy --- Production**

  -----------------------------------------------------------------------
  */deploy prod \--tag vX.Y.Z --- Per SOP-04. Confirm pre-deploy
  checkpoint, then execute blue-green.*

  -----------------------------------------------------------------------

**End of day**

  -----------------------------------------------------------------------
  */eod --- End-of-day report per SOP-06. Create end-of-day checkpoint if
  material progress.*

  -----------------------------------------------------------------------

**Weekly review**

  -----------------------------------------------------------------------
  */weekly-review --- Progress vs roadmap, decisions this week (with
  checkpoint links), top 3 risks, cost picture, checkpoint health
  (verification rituals run, any failures). Recommend adjustments.*

  -----------------------------------------------------------------------

**Recovery --- VPS restart**

  -----------------------------------------------------------------------
  */recover --- VPS was restarted. Restore state: load handoff doc,
  reload PROJECT.md, check git for current branch and in-flight work,
  verify last checkpoint, tell me what was running when we stopped.*

  -----------------------------------------------------------------------

**DR drill --- Test the failsafe**

  -----------------------------------------------------------------------
  */dr-drill \--checkpoint CP-NNN --- Restore checkpoint to a staging
  environment, run smoke tests, report success/fail. Destroy staging when
  done.*

  -----------------------------------------------------------------------

**XIII. Pre-authorized decisions**

ZeptoClaw has standing authority for these. Logged in decision log but
no Carl approval required.

  -----------------------------------------------------------------------
  **Category**                                **Authority**
  ------------------------------------------- ---------------------------
  Code style, naming, formatting              Full

  Dependency minor and patch updates          Full

  Adding logging, tests, documentation        Full

  Bug fixes that don\'t change behavior       Full

  Retry strategies, timeouts, rate limit      Full
  configs                                     

  Choosing between equivalent libraries       Full

  Vendor spend under \$25/day                 Full

  Internal refactoring without behavior       Full
  change                                      

  CI/CD pipeline adjustments                  Full

  Database index additions for performance    Full

  Checkpoint creation (routine)               Full

  Circuit breaker threshold tuning within     Full
  ±20%                                        
  -----------------------------------------------------------------------

Must escalate for:

-   Any user-facing change (UI text, voice prompts, brand)

-   Security-related changes (auth, encryption, PII handling)

-   Billing changes (Stripe, pricing, refunds, plan structure)

-   New external dependencies or vendor accounts

-   Production deploys

-   Vendor spend over \$25/day or one-time over \$100

-   Architectural changes from this document

-   New features not in the roadmap

-   Schema changes that touch existing data

-   Any rollback (always requires explicit Carl confirmation)

-   Any irreversible action

**XIV. Decision log template**

ZeptoClaw maintains the decision log in /docs/decisions/ as one markdown
file per decision. Each entry is linked to a checkpoint.

+-----------------------------------------------------------------------+
| Decision ID: D-NNN                                                    |
|                                                                       |
| Date: YYYY-MM-DD HH:MM ET                                             |
|                                                                       |
| Topic: \[short\]                                                      |
|                                                                       |
| Context: \[why this came up\]                                         |
|                                                                       |
| State at decision: CP-NNN (linked checkpoint with state, metrics,     |
| samples)                                                              |
|                                                                       |
| Options considered:                                                   |
|                                                                       |
| \- Option A: \[description, pros, cons, est. cost\]                   |
|                                                                       |
| \- Option B: \[description, pros, cons, est. cost\]                   |
|                                                                       |
| \- Option C: \[description, pros, cons, est. cost\]                   |
|                                                                       |
| Decision: \[chosen option\]                                           |
|                                                                       |
| Rationale: \[why\]                                                    |
|                                                                       |
| Recommendation by: ZeptoClaw / DeepSeek-V4-Pro investigation /        |
| \[other\]                                                             |
|                                                                       |
| Made by: Carl / ZeptoClaw (pre-auth)                                  |
|                                                                       |
| Reversibility: easy (config flag) / medium (small refactor) / hard    |
| (data migration)                                                      |
|                                                                       |
| Reversal trigger: \[metric or condition that would trigger reversal\] |
|                                                                       |
| Spec impact: \[Section X.Y updated / none\]                           |
|                                                                       |
| Post-decision CP: CP-MMM                                              |
|                                                                       |
| Linked runs: \[Run X.Y, Run X.Z\]                                     |
|                                                                       |
| Linked metrics: \[latency before/after, cost before/after, etc.\]     |
+-----------------------------------------------------------------------+

Every decision entry must include \'State at decision\' linking the
checkpoint and \'Linked metrics\' showing the hard data that justified
the decision. This is the requirement Carl articulated.

**XV. Risks & mitigations**

  ----------------------------------------------------------------------------------
  **Risk**              **Likelihood**   **Impact**   **Mitigation**
  --------------------- ---------------- ------------ ------------------------------
  Orchestrator VPS      Low              Medium       Daily snapshot + cross-region
  fails                                               replication; restore to new
                                                      VPS in \<1hr

  Backend VPS fails     Low              High         Daily snapshot + ability to
                                                      fail over to standby VPS

  Managed Postgres      Very low         Critical     HA tier with automatic
  fails                                               failover; PITR enabled

  ZeptoClaw bug halts   Low              Medium       Manual fallback: Claude Code
  orchestrator                                        via SSH; documented in
                                                      fallback runbook

  Vendor API outage     Medium           Medium       Multi-vendor fallback in voice
  (any one)                                           pipeline + circuit breakers

  Hidden costs balloon  Medium           Medium       Daily reports, \$25/day
                                                      threshold, hard caps in vendor
                                                      consoles

  Carl unavailable 48+  Medium           Medium       Pre-authorized decisions
  hours                                               handle 70%+; circuit breakers
                                                      protect production

  Bad deploy reaches    Medium           High         Pre-deploy checkpoint +
  production                                          circuit breaker + 30-min watch
                                                      window + auto-rollback
                                                      recommendation

  Schema migration      Low              High         Pre-migration checkpoint +
  corrupts data                                       dry-run on restored snapshot
                                                      before live

  Security incident     Low              Critical     ZeptoClaw container
  (intrusion)                                         isolation + Section XVI
                                                      hardening + audit

  Voice quality fails   Medium           High         Pilot in noisy bay before GA;
  in real shop                                        AssemblyAI noise model; term
                                                      injection; headset required

  Technician adoption   Medium           High         Pilot with friendly shops,
  resistance                                          iterate on voice prompts
                                                      pre-GA

  iOS App Store         Medium           Medium       Contractor for first
  rejection                                           submission (\$2-5k allocated)

  Checkpoint corruption Very low         Critical     SHA-256 manifest validation;
                                                      weekly restore drill

  ZeptoClaw memory      Medium           Low          Auto-resync from handoff doc
  drift over time                                     on weekly schedule

  Cross-region          Low              Medium       Monitored; alert if \>24hrs
  replication lag                                     behind
  ----------------------------------------------------------------------------------

**XVI. Security hardening playbook**

  -----------------------------------------------------------------------
  *Non-negotiable. v4.0\'s setup guide ran everything as root and skipped
  firewall configuration. This section corrects that. ZeptoClaw exists to
  defend against a specific threat model; building it on an unhardened
  host defeats the purpose.*

  -----------------------------------------------------------------------

**Hardening profile (both VPSes)**

**OS-level**

-   Ubuntu 24.04 LTS, fully patched at provision

-   Unattended security upgrades enabled

-   Timezone set explicitly (UTC for servers)

-   NTP synced

**User management**

-   Create dedicated non-root user (e.g., \'ari\') with sudo

-   Disable root SSH entirely

-   No password auth --- SSH keys only (ed25519)

-   One key per device; named keys; rotation log

-   Separate user for ZeptoClaw service (no sudo)

-   Separate user for backend service (no sudo)

**SSH hardening**

+-----------------------------------------------------------------------+
| \# /etc/ssh/sshd_config --- apply these settings:                     |
|                                                                       |
| PermitRootLogin no                                                    |
|                                                                       |
| PasswordAuthentication no                                             |
|                                                                       |
| PubkeyAuthentication yes                                              |
|                                                                       |
| ChallengeResponseAuthentication no                                    |
|                                                                       |
| UsePAM yes                                                            |
|                                                                       |
| X11Forwarding no                                                      |
|                                                                       |
| AllowUsers ari                                                        |
|                                                                       |
| PermitEmptyPasswords no                                               |
|                                                                       |
| Protocol 2                                                            |
|                                                                       |
| ClientAliveInterval 300                                               |
|                                                                       |
| ClientAliveCountMax 2                                                 |
|                                                                       |
| MaxAuthTries 3                                                        |
|                                                                       |
| LoginGraceTime 30                                                     |
|                                                                       |
| \# Optional: change Port from 22 to something else (e.g., 2222)       |
|                                                                       |
| \# Optional: AllowAgentForwarding no (unless explicitly needed)       |
+-----------------------------------------------------------------------+

**Firewall (UFW)**

+-----------------------------------------------------------------------+
| \# Default deny inbound, allow outbound                               |
|                                                                       |
| ufw default deny incoming                                             |
|                                                                       |
| ufw default allow outgoing                                            |
|                                                                       |
| \# Allow SSH (from your IP only if static, else any)                  |
|                                                                       |
| ufw allow from YOUR_OFFICE_IP to any port 22                          |
|                                                                       |
| \# Allow HTTPS (for FastAPI behind Caddy/Nginx)                       |
|                                                                       |
| ufw allow 443/tcp                                                     |
|                                                                       |
| \# Allow HTTP only for ACME challenge (cert renewal)                  |
|                                                                       |
| ufw allow 80/tcp                                                      |
|                                                                       |
| \# Enable                                                             |
|                                                                       |
| ufw \--force enable                                                   |
|                                                                       |
| ufw status verbose                                                    |
+-----------------------------------------------------------------------+

**Intrusion prevention**

-   fail2ban installed and configured for sshd

-   auditd installed and configured to log privileged commands

-   AIDE for file integrity monitoring on /etc, /bin, /sbin

-   Centralized logging to Datadog (sshd, auth, audit)

**ZeptoClaw-specific hardening**

-   Container isolation enabled for ALL agent execution (zeptoclaw
    config set sandbox container)

-   Sender allowlist for Telegram (only Carl\'s user ID can issue
    commands)

-   Secret encryption at rest enabled (default in ZeptoClaw)

-   Tool whitelist per agent --- researcher cannot run shell; coder can
    but only in container

-   Prompt injection detection enabled (default)

-   Webhook signatures verified on every incoming command

-   No SSH key stored in ZeptoClaw memory; uses agent-forwarded keys or
    short-lived deploy tokens

**Backend service hardening**

-   FastAPI behind Caddy reverse proxy with automatic Let\'s Encrypt

-   HSTS enabled with 1-year max-age

-   Rate limiting at proxy: 100 req/min per IP for API, stricter for
    auth endpoints

-   Request size limit: 10MB

-   CORS allowlist to dashboard origin only

-   Backend service runs as non-root user with no shell

-   Postgres connections via SSL only

-   Postgres credentials in environment via systemd, never in repo

**Secrets management**

-   DigitalOcean secret references for production keys (rotated
    quarterly)

-   ZeptoClaw secret store (XChaCha20-Poly1305 + Argon2id) for runtime
    keys

-   Master password stored in 1Password or equivalent, NEVER in repo

-   No keys in git, in env files committed, or in slack/telegram

-   Pre-commit hook: secret scanner (e.g., trufflehog)

**CI/CD pipeline security**

-   GitHub Actions deploys via short-lived deploy token, NOT a
    long-lived SSH key

-   Deploy token rotated weekly automatically

-   Production deploys require manual approval in GitHub Environments

-   Branch protection on main: required reviews, status checks, no
    force-push

**Backup security**

-   DigitalOcean Snapshots: daily, retained 14 days

-   pg_dump backups: hourly during business hours, daily otherwise

-   Backups encrypted at rest (server-side) and in transit (TLS)

-   Cross-region replication of backups bucket

-   Restore drill monthly --- destroy after verification

**Monitoring & detection**

-   Datadog: logs (sshd, auth, audit, application), metrics, traces

-   Alerts: failed login attempts, unusual command execution, port scans

-   Cost anomaly alerts (vendor spend deviation)

-   Uptime monitoring (external) for backend health endpoint

**Threat scenarios and mitigations**

  -----------------------------------------------------------------------
  **Scenario**               **Mitigation**
  -------------------------- --------------------------------------------
  SSH brute force            Key-only auth + fail2ban + UFW IP
                             restriction

  Compromised vendor API key Quarterly rotation; immediate revocation on
                             suspicion; cost cap

  Malicious LLM-generated    All agent code execution in container
  code                       isolation; PR review pattern

  Prompt injection via shop  ZeptoClaw prompt injection detection;
  data                       sandboxed execution

  Insider threat             Short-lived tokens; MFA on dashboard; audit
  (compromised laptop)       logs

  DigitalOcean account       Strong password + MFA + hardware key; alerts
  compromise                 on console login

  Supply chain attack on     Lockfile pinning; signed releases preferred;
  dependency                 renovate bot monitoring

  Database SQL injection     Parameterized queries only; ORM
                             (SQLAlchemy); WAF rules at proxy

  Data exfiltration via      Output filter on LLM responses; PII
  voice agent                redaction

  Ransomware on VPS          Daily snapshots + cross-region replication =
                             full recovery
  -----------------------------------------------------------------------

**XVII. Security, privacy & compliance**

**Data ownership**

All visual, audio, and diagnostic data collected during inspections is
owned exclusively by Workbay AI. Anonymized aggregate data may be used
to train future AI models with technician opt-in. Consent obtained via
shop subscription agreement.

**PII handling**

-   VINs encrypted at rest with envelope encryption

-   No customer names or contact info stored in MVP

-   Auth0 holds credentials; we never store passwords or hashes

-   Audio recordings retained 90 days hot; indefinite only on technician
    opt-in

-   Individual audio recordings never shared outside the company

**Transport security**

-   All API traffic over HTTPS or WSS

-   LiveKit media over DTLS-SRTP

-   Pre-signed Spaces URLs with 15-minute expiry

**Access control**

-   Auth0 for identity (OAuth2 / OIDC)

-   JWT session tokens (15-min access, 7-day refresh)

-   RBAC: technician \< advisor \< admin \< super_admin

-   Shop-scoped data isolation enforced at the database query layer

-   MFA required for super_admin and any rollback action

**Compliance posture (MVP)**

-   No HIPAA or PCI scope (Stripe handles cards; we never touch raw PAN)

-   SOC 2 Type I targeted within 6 months of launch

-   External security audit before charging customers (CP-SECAUDIT-1)

-   GDPR not in scope (US-only at launch); architecture supports it for
    future

**XVIII. Timeline & budget**

**Timeline (realistic, agent-orchestrated, checkpoint-gated)**

  ------------------------------------------------------------------------
  **Sprint**         **Agent    **Real-world      **Final Checkpoint**
                     Runs**     Duration**        
  ------------------ ---------- ----------------- ------------------------
  Sprint 0 ---       18         3-5 weeks         CP-SPRINT-0
  Foundation                                      

  Sprint 1 --- Core  40         8-12 weeks        CP-SPRINT-1
  Loop                                            

  Sprint 2 ---       22         5-7 weeks         CP-SPRINT-2
  Polish & Launch                                 
  Prep                                            

  Sprint 3 ---       15         4-5 weeks         CP-GA
  Limited GA                                      

  Total              95         5-7 months        Production GA
  ------------------------------------------------------------------------

**Budget (right-sized, honest)**

  ----------------------------------------------------------------------------
  **Category**                            **Monthly**        **One-time**
  --------------------------------------- ------------------ -----------------
  Orchestrator VPS (8GB)                  \$48               ---

  Backend VPS (16GB)                      \$96               ---

  Managed Postgres (HA tier)              \$60               ---

  DigitalOcean Spaces (data +             \$10-25            ---
  checkpoints)                                               

  Cross-region replication                \$5-15             ---

  LiveKit Cloud                           \$0-200 (variable) ---

  AssemblyAI                              \$50-200           ---

  ElevenLabs                              \$30-80            ---

  Anthropic Claude (Code + agent runtime) \$200-500          ---

  DeepSeek API (research + routine)       \$30-100           ---

  OpenAI (Codex + GPT-5 fallback)         \$50-200           ---

  Auth0 (free tier → developer tier)      \$0-25             ---

  Stripe                                  Free + 2.9% + 30¢  ---

  Vercel (free tier → Pro)                \$0-20             ---

  Datadog (Pro starter)                   \$50-100           ---

  iOS contractor (App Store submission)   ---                \$2,000-5,000

  External security audit (pre-launch)    ---                \$5,000-10,000

  DevOps part-time retainer (months 4-12) \$1,000-2,000      ---

  Buffer                                  ---                \$5,000-8,000

  Monthly run-rate (build phase)          \$650-1,500        ---

  Total to GA (\~6 months)                ---                \$28,000-45,000
  ----------------------------------------------------------------------------

Compare to v3.0 estimate (\$25-50k) and v4.0 claim (\$19-38k). v3.1
lands close to v3.0 --- that\'s because v4.0\'s lower estimate was based
on undersized infrastructure that wouldn\'t sustain the stated MVP load.
v3.1 sizes honestly.

Compare to a traditional engineering team build: \$300k-\$800k for
equivalent scope. v3.1 is 10-20x cheaper, with the trade-off being
Carl\'s sustained 20-25 hours/week.

**Appendix A: Hardened Day 1 setup**

Execute in order. Every step includes the security reasoning. If you
skip a step you weaken the system. The orchestrator VPS comes online
before the backend VPS.

**A.1 Provision orchestrator VPS**

Via DigitalOcean console:

-   Create Droplet → Ubuntu 24.04 LTS

-   Basic plan, Regular Intel with NVMe, 8GB RAM / 4 vCPU (\$48/month)

-   Region: NYC3 (or nearest to your shops)

-   Authentication: SSH key only (NO root password)

-   Add tags: orchestrator, production

-   Enable monitoring + backups

-   Create

-   Note the IP address

**A.2 First connection and user setup**

+-----------------------------------------------------------------------+
| \# From your laptop terminal:                                         |
|                                                                       |
| ssh root@ORCHESTRATOR_IP                                              |
|                                                                       |
| \# Once in, create non-root user:                                     |
|                                                                       |
| adduser ari \# use strong password                                    |
|                                                                       |
| usermod -aG sudo ari                                                  |
|                                                                       |
| \# Copy your SSH key to the new user:                                 |
|                                                                       |
| rsync \--archive \--chown=ari:ari \~/.ssh /home/ari                   |
|                                                                       |
| \# Test from your laptop (in a NEW terminal --- keep the root one     |
| open):                                                                |
|                                                                       |
| ssh ari@ORCHESTRATOR_IP                                               |
|                                                                       |
| sudo whoami \# should output: root                                    |
|                                                                       |
| \# If successful, return to the root session and disable root SSH:    |
|                                                                       |
| nano /etc/ssh/sshd_config                                             |
|                                                                       |
| \# Set: PermitRootLogin no                                            |
|                                                                       |
| \# Set: PasswordAuthentication no                                     |
|                                                                       |
| \# Set: AllowUsers ari                                                |
|                                                                       |
| \# Save and exit                                                      |
|                                                                       |
| systemctl restart sshd                                                |
|                                                                       |
| \# Test again from your laptop:                                       |
|                                                                       |
| ssh ari@ORCHESTRATOR_IP \# should still work                          |
|                                                                       |
| ssh root@ORCHESTRATOR_IP \# should now FAIL                           |
+-----------------------------------------------------------------------+

**A.3 Firewall and intrusion prevention**

+-----------------------------------------------------------------------+
| \# As ari, with sudo:                                                 |
|                                                                       |
| sudo apt update && sudo apt upgrade -y                                |
|                                                                       |
| sudo apt install ufw fail2ban auditd unattended-upgrades -y           |
|                                                                       |
| \# Configure UFW:                                                     |
|                                                                       |
| sudo ufw default deny incoming                                        |
|                                                                       |
| sudo ufw default allow outgoing                                       |
|                                                                       |
| sudo ufw allow 22/tcp \# SSH                                          |
|                                                                       |
| \# Don\'t open more ports yet --- orchestrator doesn\'t serve traffic |
|                                                                       |
| sudo ufw \--force enable                                              |
|                                                                       |
| sudo ufw status verbose                                               |
|                                                                       |
| \# Configure fail2ban:                                                |
|                                                                       |
| sudo systemctl enable fail2ban                                        |
|                                                                       |
| sudo systemctl start fail2ban                                         |
|                                                                       |
| \# Configure unattended upgrades:                                     |
|                                                                       |
| sudo dpkg-reconfigure \--priority=low unattended-upgrades             |
+-----------------------------------------------------------------------+

**A.4 Install ZeptoClaw**

+-----------------------------------------------------------------------+
| \# As ari:                                                            |
|                                                                       |
| curl -fsSL                                                            |
| https://raw.githubusercontent.com/qhkm/zeptoclaw/main/install.sh \|   |
| sh                                                                    |
|                                                                       |
| \# Run onboarding:                                                    |
|                                                                       |
| zeptoclaw onboard                                                     |
|                                                                       |
| \# During onboard, configure:                                         |
|                                                                       |
| \# - Anthropic API key (primary LLM)                                  |
|                                                                       |
| \# - DeepSeek API key (research LLM)                                  |
|                                                                       |
| \# Base URL: https://api.deepseek.com/v1                              |
|                                                                       |
| \# - Telegram channel (paste bot token from \@BotFather)              |
|                                                                       |
| \# - Telegram sender allowlist (your Telegram user ID --- get from    |
| \@userinfobot)                                                        |
|                                                                       |
| \# - Container isolation: yes                                         |
|                                                                       |
| \# - Systemd service: yes                                             |
|                                                                       |
| \# Verify:                                                            |
|                                                                       |
| zeptoclaw config show                                                 |
|                                                                       |
| zeptoclaw agent \--template researcher -m \"Say hello\"               |
+-----------------------------------------------------------------------+

**A.5 Provision backend VPS**

Repeat A.1-A.3 for the backend VPS, with these differences:

-   Size: 16GB RAM / 8 vCPU (\$96/month)

-   Tags: backend, production

-   After hardening: also allow 443/tcp and 80/tcp in UFW (for HTTPS +
    ACME)

**A.6 Provision Managed Postgres**

-   DigitalOcean console → Databases → Create

-   PostgreSQL 16, primary node in same region as VPSes

-   Plan: General Purpose / 4GB / 2 vCPU (HA tier with standby) ---
    \$60/month

-   Restrict access: VPC only, with Trusted Sources = backend VPS IP

-   Enable automated backups

-   Note connection string; store via ZeptoClaw secrets manager

**A.7 Provision Spaces buckets**

-   DigitalOcean console → Spaces → Create

-   Bucket 1: production data (photos, audio) --- versioning OFF

-   Bucket 2: checkpoints --- versioning ON, lifecycle rules per Section
    XI

-   Generate Spaces access keys; store via ZeptoClaw secrets

**A.8 Configure ZeptoClaw secrets store**

+-----------------------------------------------------------------------+
| \# On orchestrator VPS, as ari:                                       |
|                                                                       |
| zeptoclaw secrets set                                                 |
|                                                                       |
| \# Will prompt for each. Add:                                         |
|                                                                       |
| \# LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET                   |
|                                                                       |
| \# ASSEMBLYAI_API_KEY                                                 |
|                                                                       |
| \# ELEVENLABS_API_KEY                                                 |
|                                                                       |
| \# AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET                 |
|                                                                       |
| \# STRIPE_SECRET_KEY                                                  |
|                                                                       |
| \# DATABASE_URL                                                       |
|                                                                       |
| \# SPACES_ACCESS_KEY, SPACES_SECRET_KEY                               |
|                                                                       |
| \# ANTHROPIC_API_KEY (already done in onboarding)                     |
|                                                                       |
| \# DEEPSEEK_API_KEY (already done in onboarding)                      |
|                                                                       |
| \# OPENAI_API_KEY (for Codex + fallback)                              |
|                                                                       |
| \# Master password: store in 1Password ONLY. Never in repo, never in  |
| chat.                                                                 |
|                                                                       |
| \# Test retrieval:                                                    |
|                                                                       |
| zeptoclaw secrets get LIVEKIT_URL                                     |
+-----------------------------------------------------------------------+

**A.9 Project repository**

+-----------------------------------------------------------------------+
| \# On your laptop:                                                    |
|                                                                       |
| mkdir -p \~/projects/auto-inspection                                  |
|                                                                       |
| cd \~/projects/auto-inspection                                        |
|                                                                       |
| git init                                                              |
|                                                                       |
| gh repo create auto-inspection \--private \--source=.                 |
| \--remote=origin                                                      |
|                                                                       |
| \# Set branch protection on main via GitHub UI:                       |
|                                                                       |
| \# - Require pull request reviews before merging                      |
|                                                                       |
| \# - Require status checks to pass                                    |
|                                                                       |
| \# - Disable force push                                               |
|                                                                       |
| \# - Restrict who can push to main                                    |
|                                                                       |
| \# Add this handoff doc:                                              |
|                                                                       |
| mkdir -p docs                                                         |
|                                                                       |
| cp \~/Downloads/handoff_v3.1.docx docs/handoff_v3.1.docx              |
|                                                                       |
| git add docs/handoff_v3.1.docx                                        |
|                                                                       |
| git commit -m \"Initial: handoff doc v3.1\"                           |
|                                                                       |
| git push -u origin main                                               |
+-----------------------------------------------------------------------+

**A.10 Day 1 onboarding prompt**

On your phone, open Telegram, find your ZeptoClaw bot. Send the Day 1
prompt from Section XII.

**A.11 First checkpoint**

Once ZeptoClaw confirms it\'s loaded the doc and you\'ve answered its 10
onboarding questions, send:

  -----------------------------------------------------------------------
  */checkpoint create \"CP-0003: handoff doc loaded, onboarding decisions
  logged, infrastructure provisioned\"*

  -----------------------------------------------------------------------

This is your first hard data point to return to. Sprint 0 begins from
here.

**Appendix B: Tool URLs and signup links**

  --------------------------------------------------------------------------
  **Tool**         **URL**                     **Purpose**
  ---------------- --------------------------- -----------------------------
  ZeptoClaw        github.com/qhkm/zeptoclaw · Master orchestrator
                   zeptoclaw.com               

  DigitalOcean     digitalocean.com            VPS, Managed DB, Spaces

  Claude / Claude  claude.ai · docs.claude.com Primary LLM + coding agent
  Code                                         

  DeepSeek         platform.deepseek.com       Research LLM + cost-efficient

  Codex            platform.openai.com         Async coding agent

  Cursor           cursor.sh                   Visual code review

  Vapi             vapi.ai                     Voice flow prototyping

  Lovable          lovable.dev                 Dashboard mockups

  v0               v0.dev                      React component generation

  FlutterFlow      flutterflow.io              Flutter app builder

  Abacus AI        abacus.ai                   Rapid app builder

  LiveKit          livekit.io                  Voice infrastructure

  AssemblyAI       assemblyai.com              STT

  ElevenLabs       elevenlabs.io               TTS

  Vercel           vercel.com                  Dashboard hosting

  Auth0            auth0.com                   Authentication

  Stripe           stripe.com                  Payments

  Datadog          datadoghq.com               Observability

  GitHub           github.com                  Code repository

  1Password        1password.com               Master password vault
  --------------------------------------------------------------------------

**Appendix C: Example inspection flow**

+-----------------------------------------------------------------------+
| App TTS: \"Vehicle confirmed: 2019 Honda Accord, 84,000 miles.        |
|                                                                       |
| Customer concern: brake noise. Starting inspection.                   |
|                                                                       |
| Please move to the front left wheel and inspect                       |
|                                                                       |
| the brake pads.\"                                                     |
|                                                                       |
| Tech: \"Front left pad is at 4 millimeters. Rotor\'s got              |
|                                                                       |
| a lip but no scoring.\"                                               |
|                                                                       |
| System: \[STT transcribes; LLM extracts pad_thickness=4mm,            |
|                                                                       |
| rotor condition=fair; calls save_finding(\...)\]                      |
|                                                                       |
| App TTS: \"Got it. Pad thickness 4 millimeters, rotor has             |
|                                                                       |
| a wear lip. Please take a photo of the brake                          |
|                                                                       |
| assembly when you\'re ready.\"                                        |
|                                                                       |
| Tech: \[taps camera, takes photo\]                                    |
|                                                                       |
| App TTS: \"Photo received. Any uneven wear on the pads,               |
|                                                                       |
| or signs of caliper sticking?\"                                       |
|                                                                       |
| Tech: \"No, looks even. Caliper slides feel okay.\"                   |
|                                                                       |
| System: \[Saves no_uneven_wear=true, caliper_condition=good\]         |
|                                                                       |
| App TTS: \"Front left brakes complete. Moving to front right\...\"    |
+-----------------------------------------------------------------------+

**Appendix D: Technology evaluation rationale**

**Why ZeptoClaw over OpenClaw**

OpenClaw has had real security events: CVE-2026-25253 (CVSS 8.8,
cross-site WebSocket hijacking to RCE), ClawHavoc supply chain attack
(341 malicious skills, 9,000+ compromised installs), and 42,000 exposed
instances with auth bypass. ZeptoClaw was built explicitly against this
threat model: XChaCha20-Poly1305 secret encryption at rest, container
isolation, prompt injection detection, deny-by-default sender
allowlists. 4-6MB Rust binary, MIT-licensed, active development. Drop-in
replacement via \`zeptoclaw migrate\`. For a system that will hold VINs
and Stripe keys, this is the right risk posture.

**Why DeepSeek-V4-Pro for research and routine LLM work**

Released April 2026. 1M context window by default. 1.6T total parameters
with 49B active (MoE). MIT-licensed open weights with hosted API.
Pricing \~8-9x cheaper than Claude Opus 4.7 on output (\$1.74 / \$3.48
per M tokens vs. Opus 4.7\'s much higher rates). For non-realtime work
--- vendor research, document analysis, test data generation --- the
cost gap dominates the decision. Claude remains primary for production
voice agent because tool-use reliability and latency matter more than
cost in the hot path.

**Why two VPSes instead of one**

Blast radius isolation. If the orchestrator misbehaves it should not
take down the production voice pipeline. Operationally: orchestrator
restarts and deploys happen frequently during the build; the backend
should not see those. Cost difference vs single VPS: \~\$60/month ---
worth it for the isolation alone.

**Why DigitalOcean over AWS**

Simpler pricing, simpler operations, lower learning curve for a solo
orchestrator-led build. AWS would be the right call for a team with
dedicated DevOps; for this build the cognitive overhead of AWS isn\'t
paid back. DigitalOcean Spaces is S3-compatible, so migration to AWS
later is straightforward if scale demands it.

**Why LiveKit over Vapi**

Full control over orchestration logic --- which is the IP of the
product. Vapi bundles voice transport at \$0.07-\$4.50/hour, which at
6-hour shifts × 150 technicians becomes \$190k-\$1.2M/year. LiveKit at
usage rates plus separate STT/LLM/TTS billing is significantly cheaper
at scale.

**Why AssemblyAI over Deepgram**

Lowest WER among major providers, turn-by-turn term injection up to
1,000 terms (critical for automotive vocabulary), strong on noisy shop
audio. Deepgram is configured as fallback for capacity overflow.

**Why Claude over GPT-5 (primary voice path)**

Claude consistently outperforms in structured tool-use reliability and
following operational protocols --- both critical for the inspection
orchestrator. GPT-5 configured as fallback via LiveKit router for
capacity and redundancy.

**Why Flutter over React Native**

More mature audio routing on both platforms; official LiveKit SDK;
better Bluetooth headset handling in noisy environments.

**Why Postgres + JSONB + pgvector over MongoDB**

JSONB columns give MongoDB-style flexibility without operating two
databases. pgvector enables Phase 2 RAG. Transactional consistency
across structured + semi-structured data.

**Why checkpoint-based failsafe**

Per Carl: \"failsafe update handoff or current data at each decision
point so that we have hard data points to return to during the build if
anything goes sideways.\" Every decision links to a checkpoint capturing
the state, metrics, and samples that justified it. Every checkpoint is
restorable. The system has no irreversible state by default --- only
explicit acknowledgments flag a change as irreversible.

**Why modular monolith over microservices**

Microservices add 5x operational overhead with no functional benefit at
MVP scale. A modular monolith with clear domain boundaries is faster to
ship, easier to refactor, and trivially splittable when load justifies
it.

**Appendix E: Glossary**

  -----------------------------------------------------------------------
  **Term**           **Definition**
  ------------------ ----------------------------------------------------
  Agent run          A single ZeptoClaw-orchestrated execution unit,
                     typically 30 min - 4 hours

  Barge-in           User interrupting the agent mid-speech

  Checkpoint         Time-stamped, content-hashed snapshot of full
                     project state (Section XI)

  Circuit breaker    Automated trigger that recommends rollback when
                     metrics exceed thresholds

  DelegateTool       ZeptoClaw feature for parallel fan-out to specialist
                     sub-agents

  DR drill           Disaster recovery drill --- restore checkpoint to
                     staging, verify, destroy

  DTLS-SRTP          Encrypted media transport protocol used by WebRTC

  DVI                Digital Vehicle Inspection

  Endpointing        Detecting the end of a user\'s speech turn

  JSONB              Postgres binary JSON type with indexing

  KMS                Key Management Service; manages encryption keys

  LiveKit Agents     Python framework for building voice AI pipelines

  MTTD / MTTR        Mean Time To Detect / Mean Time To Recover

  OBD2               On-Board Diagnostics II; vehicle diagnostic standard

  Orchestrator       Meta-agent that dispatches and supervises other
                     agents (here: ZeptoClaw)

  PAN                Primary Account Number (credit card number)

  pgvector           Postgres extension for vector embedding search

  RAG                Retrieval-Augmented Generation; LLM grounding via
                     document retrieval

  RPO / RTO          Recovery Point Objective / Recovery Time Objective

  SFU                Selective Forwarding Unit; WebRTC media routing

  Sprint             Logical grouping of agent runs toward a milestone
                     (not a calendar week)

  STT / ASR          Speech-to-Text / Automatic Speech Recognition

  TSB                Technical Service Bulletin (manufacturer)

  TTS                Text-to-Speech

  VAD                Voice Activity Detection

  VPS                Virtual Private Server

  WER                Word Error Rate; STT accuracy metric (lower is
                     better)
  -----------------------------------------------------------------------

*--- End of AI Workforce Handoff v3.1 (Synthesis Edition) ---*
