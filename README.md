# PRD: PII Discovery & DSR Orchestrator

**Team:** 08/8
**Problem statement:** #16 (Data Privacy: GDPR / DPDP Act compliance)
**Goal:** Working MVP demo on **Monday, 30 November 2026**
**Status:** Draft v1.0
**Product name:** Lethexa

---

## 1. What we are building (in simple words)

Companies store customers' personal data (phone numbers, emails, Aadhaar-style IDs, etc.) in many places. Privacy laws like India's DPDP Act say a customer can ask the company to **show** or **delete** their data. Most companies don't know where all that data is.

Our tool does two things:

1. **Find it:** connect to a database (read-only), scan it, and show a **map** of where personal data lives.
2. **Handle requests:** when a customer asks for deletion, find their data, show a **preview** of what will be deleted, get a **human approval**, delete safely, and produce an **evidence report**.

Our tool **supports** compliance. It does **not** certify anything or guarantee compliance.

---

## 2. Deadline and what the demo must show

We have until **30 Nov 2026** (about 11 days from 19 Nov). That is short, so the MVP is a **thin end-to-end slice**: one path that works well, not many half-working features.

### The demo story (8 steps)

| Step | What the audience sees |
|---|---|
| 1 | Connect to a PostgreSQL database (read-only user) |
| 2 | Run a scan in the background |
| 3 | See the **data map**: tables, columns, PII type, confidence |
| 4 | Create a **deletion request** for one customer (e.g. an email) |
| 5 | Complete the **verification** step |
| 6 | See the **dry-run preview**: exactly what would be deleted |
| 7 | A reviewer **approves**; the deletion runs safely (and rolls back on error) |
| 8 | Download the **evidence report**; show the **audit log** |

If all 8 steps work on synthetic data, the MVP is a success.

---

## 3. Scope

### Must have (P0): the demo cannot happen without these
- PostgreSQL connector (read-only): connect, read schema, sample rows
- Rule-based PII detectors: email, phone, PAN, Aadhaar-style number, credit card
- Every finding has a **category, confidence and reason**
- Scan runs as a background job; **only findings are stored, never raw PII**
- Data map dashboard
- Request flow: create, verify (manual checklist), locate records, dry-run, approve, delete
- Delete inside a database transaction (rolls back on error)
- Audit log (each entry linked to the previous one so tampering is detected)
- Evidence report (PDF) for each completed request
- Simple login (one workspace is enough)
- Synthetic test dataset (start with about 10 tables; grow toward 50 only if time allows)

### Stretch (P1): only after all P0 items are stable
- S3 connector (read CSV/JSON/TXT files)
- NLP classifier for names and addresses
- S3 deletion, access/export request, email OTP verification

### Not now
- Warehouses (Snowflake, BigQuery), MongoDB, MySQL
- Deleting from backups
- SSO, multiple organisations, advanced roles
- Real customer data (never)

---

## 4. How it works

```
Customer database (PostgreSQL)
        |  read-only
        v
 [Connector] --> [Scanner + Detectors] --> [Findings DB: where PII is, no raw values]
                                                  |
                                                  v
                                          [Data Map Dashboard]

Deletion request:
 Create -> Verify -> Locate records -> Dry-run preview -> Approve -> Delete -> Evidence report
                                                  |
                                       (every step goes into the Audit Log)
```

### Building blocks
| Block | What it does |
|---|---|
| Connector | Safely reads schema and sample rows (read-only) |
| Detectors | Rules that spot PII and give category, confidence and reason |
| Findings DB | Stores where PII is (table, column, type, confidence), not the data itself |
| Request engine | Moves a request through its states and checks approvals |
| Audit log | Records who did what and when; tamper-evident |
| Evidence report | PDF with the request history, worded as supporting evidence |
| Web app | Data map, request tracker, approval screen, report download |

### Request states
`Received` -> `Verified` -> `Located` -> `Plan ready` -> `Approved` -> `Executed` -> `Report ready`

---


## 5. How we work

**Git in 5 steps**
1. `git pull` on `main`
2. Create a branch: `git checkout -b yourname/short-task` (e.g. `mahathi/email-detector`)
3. Make small changes, commit often with clear messages
4. Push and open a **pull request**
5. One teammate reviews; CI must pass; then merge

**Rules**
- Never push directly to `main`.
- Tasks live on the shared board: To do, In progress, In review, Done.
- **Daily 10-minute check-in:** what I finished, what I'm doing, where I'm blocked.
- Blocked for more than 24 hours? Say so in the team chat immediately.
- Decisions go in the decision log. If the team can't agree within a day, Kanai Das decides.
- **Definition of Done:** reviewed, tests pass, no secrets committed, documented, demoed to the team.
- Keep a working end-to-end path at all times.

### Suggested repo layout
```
/backend        API, request engine, scan jobs
/connectors     Postgres (and S3 if time)
/detectors      PII rules and tests
/frontend       Dashboard and request screens
/data           Synthetic data generator (no real data)
/docs           prd.md, threat-model.md, dpdp-summary.md, decision-log.md
README.md       How to set up and run in a few commands
```

---

## 6. Ground rules (non-negotiable)

1. **No real personal data in development, ever.** Synthetic data only.
2. **Deletion is always dry-run first and needs human approval.**
3. **Read-only credentials for scanning.** A separate, narrowly scoped credential is used only for approved deletions.
4. **Pilots need a written agreement** with each startup before the tool connects to any real system.
5. **We never claim certification or guaranteed compliance.** Our reports are supporting evidence.
6. **No secrets in the repo.** Use environment variables.

---

## 7. If we fall behind

Cut in this order, and **never** cut the last three:

1. S3 connector
2. NLP classifier
3. Extra detectors beyond email, phone, PAN
4. Number of synthetic tables (fewer is fine)
5. Polish on the UI

**Never cut:** dry-run preview, human approval, audit log. These are the heart of the product and the demo.

---

## 8. Proposed tech stack (confirm on 19 to 20 Nov)

| Part | Suggestion |
|---|---|
| Backend | Python with FastAPI |
| Background jobs | Simple background tasks first; add a queue only if needed |
| Findings / app database | PostgreSQL |
| Detectors | Python regex plus validators (Luhn for cards) |
| Frontend | React (Vite) |
| PDF report | A Python PDF library (e.g. ReportLab) |
| Test data | Faker, with Indian-style formats |
| Environment | Docker Compose |
| CI | GitHub Actions |

Choose what most of the team already knows. Familiar tools beat ideal tools when time is short.

---

## 9. What we store (and don't)

| Stored | Not stored |
|---|---|
| Source, table, column, PII category, confidence, reason | Raw PII values |
| Request status, who approved, timestamps | Customer identifiers longer than needed (store hashed or minimal) |
| Audit log entries | Credentials in plain text |

---

## 10. Risks

| Risk | What we do |
|---|---|
| Not enough time (11 days) | Thin slice scope, freeze on 28 Nov, cut list in Section 11 |
| Unsafe deletion bug | Dry-run, approval, transactions, forced-failure test |
| Detectors give wrong results | Show confidence and reason; measure against labelled data |
| Someone is busy or unavailable | Every area has a backup; use the board to see gaps early |
| Legal misunderstanding | Manoj's DPDP summary; ask a faculty or privacy adviser to review before any pilot |
| Integration problems late | Build against mock data early; check-ins on 22, 24 and 27 Nov |

---

## 11. Open decisions (decide by 20 Nov)

1. Tech stack confirmed? (Section 12)
2. Hosting after the demo: self-hosted, SaaS, or both? (Does not affect the demo)
3. Roles confirmed as in Section 5?
4. Which sector do we target first for pilots? (After the demo)

---

## 12. After the demo (stretch, not for November)

- Customer interviews: script and a list of 10 people (Kanai Das)
- Product name shortlist and availability checks (Kanai Das, Sampurn Alok)
- Pilot agreements with startups or the college incubator (Kanai Das, Manoj Godiya)
- S3 support, NLP classifier, access/export requests, more databases
