PRD: PII Discovery & DSR Orchestrator

Team: 08/8
Source: Problem Statement #16, Data Privacy and GDPR/DPDP Act Compliance

1. Overview
1.1 One-line pitch

An agentless tool that finds where a company's customer personal data (PII) lives across its databases and storage, and automates verified access and deletion requests with an audit trail.

1.2 Problem

Privacy laws (India's DPDP Act, EU GDPR, California CCPA) give people the right to access and erase the personal data a company holds about them. Companies usually do not know where that data is: it is spread across production databases, cloud storage, warehouses, logs and exports. Manual discovery is slow and incomplete, so requests are handled badly and the company risks fines (the problem statement cites up to Rs 250 crore under the DPDP Act) and loss of customer trust.

1.3 Our solution
Discover: connect read-only to data sources, scan them, and classify PII into a data map.
Act: when a person submits a request, locate their records using the data map, run an approved deletion or export workflow, and produce evidence.
1.4 Why us, why now
DPDP compliance is a new obligation for Indian companies, and many are unprepared.
Large incumbents (OneTrust, BigID, Securiti) are enterprise-priced. There is room for a simple, affordable, India-first tool for small and mid-sized companies.
The core build (connectors, classification, workflow, dashboard) is achievable for an intermediate student team.
2. Goals and Non-Goals
2.1 Goals (MVP demo at the end of this month)
G1: Scan a PostgreSQL database and an S3 bucket and produce a PII map with confidence scores.
G2: Let a compliance user submit and process a deletion request end to end for PostgreSQL, with human approval.
G3: Produce an audit log and a downloadable evidence report per request.
G4: Deliver a working, demo-ready MVP on synthetic data. Real pilots with startups or the college incubator come after the demo.
G5: Store findings only (where PII is), never raw PII values.
2.2 Non-Goals (explicitly not in MVP)
Warehouses (Snowflake, BigQuery), SaaS app connectors, email or file-server scanning.
Fully automatic deletion without human approval.
Deleting from backups and archived logs.
Enterprise features: SSO, advanced RBAC, multi-region deployment.
Legal advice, official certification, or any guarantee of compliance. The tool supports compliance and produces evidence; only regulators and licensed auditors certify.
3. Users and Personas
Persona	Role	What they need
Compliance Lead (primary buyer/user)	Legal, compliance or data-protection owner at a 50-1,000 person company	See where PII lives, process requests on time, show evidence to auditors
Engineer / Data Owner	Backend or data engineer	Safe, read-only setup; clear deletion plan before anything changes
Founder / CTO (early-stage)	Decision maker at a small startup	Fast setup, low cost, confidence they will not be caught off guard
Data Principal (end customer)	Person whose data is held	Submit a request and get a clear outcome
4. User Stories

Discovery

As a compliance lead, I want to connect a database with a read-only credential so that nothing can be changed by the tool.
As a compliance lead, I want a map of which tables, columns and files contain which PII categories so that I know our exposure.
As an engineer, I want to see why a column was flagged (rule or model, confidence) so that I can verify it.
As an engineer, I want to mark a finding as false positive or confirmed so that results improve over time.

Requests (DSR)

As a compliance lead, I want to log a deletion or access request with the requester's identifier so that it is tracked.
As a compliance lead, I want the tool to locate every record linked to that person across connected sources.
As an engineer, I want a preview (dry run) of exactly what will be deleted before approving it.
As a compliance lead, I want a deadline and status for each request so that none are missed.

Evidence

As a compliance lead, I want a tamper-evident audit log and a downloadable report per completed request to show auditors.

Admin

As an admin, I want to invite team members and set simple roles so that only authorised people approve deletions.
5. Functional Requirements

Priority: P0 = must have for the MVP demo, P1 = should have if time allows, P2 = later.

5.1 Connectors
ID	Requirement	Priority
F-1	Connect to PostgreSQL using a read-only user	P0
F-2	Connect to an S3 bucket (or S3-compatible store) with a read-only IAM role	P0
F-3	Test-connection check with clear error messages	P0
F-4	MySQL connector	P1
F-5	MongoDB connector	P2
5.2 Scanning and classification
ID	Requirement	Priority
F-6	Read schema metadata (tables, columns, types)	P0
F-7	Sample rows safely (limit, no full copy) and classify columns	P0
F-8	Rule-based detection with validators for email, phone, PAN, Aadhaar-style numbers (checksum where applicable), credit card (Luhn)	P0
F-9	NLP classifier for names and addresses	P1
F-10	Confidence score and detection reason on every finding	P0
F-11	Scan S3 text-based files (CSV, JSON, TXT, logs)	P0
F-12	Re-scan on demand and on a schedule, with a change report	P1
F-13	User feedback on findings (confirm / false positive)	P1
5.3 Data map
ID	Requirement	Priority
F-14	Dashboard listing sources, tables, columns, PII categories and confidence	P0
F-15	Filters by source, category and confidence	P1
F-16	Export data map as CSV or PDF	P1
5.4 DSR workflow
ID	Requirement	Priority
F-17	Create request (type: delete or access; identifier: email or phone)	P0
F-18	Requester identity verification step (for MVP: email OTP or manual verification checklist)	P0
F-19	Locate matching records across connected PostgreSQL sources using the data map	P0
F-20	Generate a deletion plan with dry-run preview, including related-table impact	P0
F-21	Approval by an authorised user before execution	P0
F-22	Execute deletion in PostgreSQL inside a transaction with rollback on error	P0
F-23	Access request: export the person's data as a structured file	P1
F-24	Request states: Received, Verified, Located, Plan ready, Approved, Executed, Evidence ready, with due date tracking	P0
F-25	S3 object deletion workflow	P1
5.5 Audit and evidence
ID	Requirement	Priority
F-26	Append-only audit log (who, what, when) with hash chaining for tamper evidence	P0
F-27	Per-request audit-ready evidence report (PDF). This is supporting evidence, not an official certification	P0
5.6 Admin
ID	Requirement	Priority
F-28	Sign-up, login, organisation workspace	P0
F-29	Roles: Admin, Reviewer, Viewer	P1
6. Non-Functional Requirements
Area	Requirement
Security	Read-only access to sources; credentials encrypted at rest; TLS everywhere; no raw PII stored in our metadata store; secrets never in code or logs
Privacy	Sampled values are processed in memory and discarded; logs must be scrubbed of PII; data minimisation by default
Reliability	Scans run as background jobs with retry; a failed deletion must roll back cleanly
Performance	Scan of a sample database (about 50 tables, 1M rows) completes within 15 minutes for MVP
Accuracy	Target at least 90% precision on rule-detected categories and at least 80% recall on the synthetic benchmark
Usability	A new user can connect a source and see a PII map in under 15 minutes
Auditability	Every action on a request is recorded and exportable
Maintainability	Tests for detectors and workflow; documented setup; CI on every pull request
7. Solution Approach
7.1 System architecture (logical)
[Web Dashboard]  <->  [API Server]  <->  [Metadata DB (findings, requests, audit)]
                           |
                      [Job Queue]
                           |
              +------------+-------------+
              |                          |
        [Scanner Workers]         [DSR Workers]
              |                          |
     [Connectors: Postgres, S3]   [Execute deletion / export]
              |                          |
        Customer data sources (read-only for scan; scoped write for approved deletion)
7.2 Key components
Connector layer: one interface (connect, list_schema, sample, search_by_identifier, delete) with an implementation per source.
Detection engine: pipeline of (a) column-name hints, (b) regex and validators on sampled values, (c) optional NLP model. Combines signals into a confidence score.
Metadata store: findings only: source, table, column, category, confidence, reason. No raw values.
DSR workflow engine: state machine for requests with approvals and due dates.
Audit service: append-only log with hash chaining; generates the evidence PDF.
Web app: dashboard, data map, review queue, request tracker.
7.3 Important design decisions
Findings, not data: we store where PII is, not what it is.
Separate credentials: a read-only credential for scanning; a separate, narrowly scoped credential for deletion that is only used after approval.
Dry run first: every deletion shows a preview and needs human approval.
Transactional deletes: delete inside a transaction; commit only if all steps succeed.
Explainable detection: every finding says why it was flagged.
7.4 Suggested tech stack (adjust as a team)
Layer	Suggestion	Reason
Backend API	Python (FastAPI)	Quick to build; good data and ML libraries
Job queue	Celery + Redis (or RQ)	Simple background scanning
Metadata DB	PostgreSQL	Familiar, reliable
Detection	Regex + validators; spaCy or a small transformer for names/addresses	Practical on a student budget
Frontend	React (or Next.js) + a component library	Fast dashboard development
Auth	A managed or library-based auth (avoid writing your own)	Security
Infra	Docker Compose for dev; one cloud VM or free-tier hosting for the demo	Low cost
CI/CD	GitHub Actions	Free for students
Testing data	Faker-generated synthetic customer data	No real PII in development
8. Data Model (high level)
Organisation (id, name)
User (id, org, email, role)
DataSource (id, org, type, connection ref, status, last_scan)
Scan (id, source, started, finished, status)
Finding (id, scan, location path, category, confidence, reason, review_status)
Request (id, org, type, identifier hash, status, due_date, created_by)
RequestAction (id, request, step, result, actor, timestamp)
AuditEvent (id, org, actor, action, payload, timestamp, prev_hash, hash)

Note: request identifiers (email or phone) should be stored hashed or minimally and deleted per a retention policy.

9. Security and Privacy Threat Considerations
Threat	Mitigation
Our platform becomes a honeypot of customer data	Store findings only; encrypt; minimal retention
Stolen source credentials	Encrypted secret storage; read-only roles; rotation guidance
Accidental or malicious deletion	Dry run, approval, role checks, transactions, audit log
PII in our own logs	Log scrubbing, structured logging review
Insecure uploads or injection	Input validation, parameterised queries, dependency scanning
Weak internal access	MFA for admins, least privilege for team accounts

The team should run a short threat-modelling session at the start of the build and re-check before the demo.

10. Success Metrics (MVP demo)
Metric	Target (MVP)
Time to first PII map	under 15 minutes from sign-up
Detection precision / recall (synthetic benchmark)	at least 90% / 80%
Deletion workflow success rate in tests	100% rollback on failure, 0 unintended deletes
Live demo	Full flow works end to end: connect, scan, data map, request, dry run, approve, delete, evidence report
Test coverage on detectors and workflow	at least 70% (stretch if time is short)

After the demo (stretch): at least 2 pilots, at least 1 pilot saying they would keep using it, and at least 10 customer interviews.

11. Build Order

The MVP is due at the end of this month, so the build is organised by order of dependency, not by calendar. Each stage should be demoable before the next one starts.

Stage	Focus	Deliverables
1. Setup	Foundations	Roles assigned, repo and CI, tech stack agreed, synthetic dataset, short threat model, DPDP summary
2. Discovery MVP	Find the PII	Postgres + S3 connectors, rule-based detector, scan jobs, basic data map
3. DSR MVP	Act on a request	Request intake, verification, locate, dry run, approval, transactional delete, audit log
4. Evidence and polish	Prove it	Evidence PDF, security hardening, docs, demo script. NLP classifier only if time allows (P1)
5. Demo	Show it	Rehearsed MVP demo and pitch

Scope rule for the demo: only P0 items must work. P1 items are added only after all P0 items are stable.

12. Risks and Mitigations
Risk	Likelihood	Impact	Mitigation
Scope creep	High	High	Hold to the P0 list; new ideas go to a backlog
Not finishing by the demo date	High	High	Build in demoable stages; cut P1 items first; keep a working end-to-end path at all times
Unsafe deletion bug	Medium	High	Dry run, approvals, transactions, thorough tests on synthetic data
Classifier accuracy too low	Medium	Medium	Start rules-first; add human review and feedback
Legal misunderstanding of DPDP	Medium	High	Read the Act and rules; get a privacy or legal professional to review workflows; state clearly we do not guarantee compliance
No pilot customers	Medium	Medium	Start interviews early; use college incubator and club network; demo on synthetic data meanwhile
Team availability (exams, deadlines)	High	Medium	Keep tasks small; every area has a backup; pair on critical parts
Incumbent competition	Medium	Medium	Niche focus: small/mid-sized Indian companies, DPDP-first, simple pricing
Security incident in our own platform	Low	High	Security-first design, minimal data, dependency scanning
13. Assumptions and Dependencies
Team has access to free-tier cloud credits or student programs for hosting and an S3-compatible service.
Synthetic data is acceptable for development and the MVP demo; any real pilot will need a written agreement before touching real systems.
Current DPDP Act rules and timelines will be verified from official government sources.
At least one adviser (faculty, mentor or privacy professional) can review the workflow for legal accuracy.
14. Open Questions
Which sector do we target first: fintech, e-commerce or health-tech?
DPDP-first positioning only, or DPDP plus GDPR from the start?
Pricing model: per data source, per request, or flat subscription?
Hosting: SaaS only, self-hosted only, or both? Self-hosting keeps customer data inside their environment, but means we must support installs and upgrades on their infrastructure. Current working assumption: self-hosted first.
Product name and branding.
15. Ground Rules (non-negotiable)
No real personal data in development, ever. Synthetic data only.
Deletion is always dry-run first and needs human approval.
Read-only credentials for scanning. A separate, narrowly scoped credential is used only for approved deletions.
Pilots need a written agreement with each startup before the tool connects to any real system.
We never claim certification or guaranteed compliance. Our reports are supporting evidence.
No secrets in the repo (keys, passwords, tokens). Use environment variables or a secrets manager.
  cript early so the build stays focused on what will be shown.
