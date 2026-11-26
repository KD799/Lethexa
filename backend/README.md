# Lethexa – PII Discovery & DSR Orchestrator

## Overview

Lethexa is a backend system designed to help organizations discover Personally Identifiable Information (PII) and manage Data Subject Requests (DSRs), such as requests to access or delete personal data.

It provides a structured workflow for request verification, PII discovery, data location, deletion execution, audit logging, and evidence report generation.

## Key Features

- **DSR Management:** Create and manage data subject requests.
- **Identity Verification:** Verify requesters using OTP-based email verification.
- **PII Discovery:** Scan configured data sources to identify personal information.
- **Subject Locator:** Find records associated with a particular individual.
- **Deletion Preview:** Preview matching records before deletion.
- **Controlled Deletion:** Support dry-run and permanent deletion execution.
- **Audit Logging:** Maintain records of important workflow activities.
- **Evidence Reports:** Generate reports documenting request processing and deletion outcomes.
- **Authentication:** Secure API access using JWT authentication and password hashing.

## Workflow

1. Submit a data subject request.
2. Verify the requester's identity.
3. Discover PII in the configured data sources.
4. Locate records belonging to the requester.
5. Preview the records before deletion.
6. Execute a dry run or authorized permanent deletion.
7. Generate an evidence report and maintain audit records.

## Technology Stack

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL
- **Authentication:** JWT, Argon2 password hashing
- **Cloud Storage Integration:** S3-compatible storage using Boto3
- **API Documentation:** Swagger UI
- **Testing:** Pytest

## Project Structure

```text
Backend/
├── app/
│   ├── api/
│   ├── connectors/
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.10 or newer
- PostgreSQL
- Git
- A configured S3-compatible storage service (if using storage scanning)

## Installation

Clone the repository:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd Backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Configuration

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Configure the required database, authentication, and email settings in `.env`.

The application uses two PostgreSQL databases:

- `lethexa_app` – application data, requests, workflow records, and audit information.
- `lethexa_source` – source data used for PII discovery and controlled deletion.

Configure separate database credentials for the read-only scanner and deletion executor.

**Important:** Never upload your actual `.env` file, database passwords, JWT secrets, or email credentials to GitHub.

## Running the Application

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

## Testing

Run the test suite using:

```bash
pytest
```

## Security Considerations

- Use separate database credentials for scanning and deletion.
- Keep scanner permissions read-only.
- Restrict deletion permissions to explicitly approved tables.
- Keep secrets in environment variables.
- Verify requester identity before processing sensitive requests.
- Maintain audit records and evidence reports for accountability.

## Project Status

The core PostgreSQL-based PII discovery and DSR deletion workflow has been tested, including identity verification, record location, dry-run deletion, permanent deletion, and evidence report generation.

Some integrations and deployment configurations may require additional setup.

## Disclaimer

This project is developed for educational and demonstration purposes. Production deployment requires additional security reviews, access controls, monitoring, and compliance validation.
