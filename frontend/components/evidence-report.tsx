"use client"

import { useMemo, useState } from "react"
import { Check, Download, FileCheck2, Printer } from "lucide-react"

type RequestRecord = { id: string; identifier: string; type: "Access" | "Delete"; date: string; verification: string; status: string }

const sections = ["Executive summary", "Request details", "PII discovery results", "Approval and execution", "Audit trail", "Evidence summary"]
const demoFindings = [
  { source: "Production · PostgreSQL", database: "customer_prod", table: "customers", column: "email_address", category: "Email", records: 2, confidence: "99%", reason: "Column name and format match" },
  { source: "Analytics · Snowflake", database: "warehouse", table: "dim_users", column: "full_name", category: "Name", records: 1, confidence: "96%", reason: "Common personal name field" },
  { source: "Backup · Amazon S3", database: "data-lake", table: "exports_2025", column: "identity_ref", category: "Identifier", records: 1, confidence: "89%", reason: "Sensitive identifier pattern" },
]
const reportId = () => `LX-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}-${crypto.randomUUID().slice(0, 8).toUpperCase()}`

export function EvidenceReport({ requests }: { requests: RequestRecord[] }) {
  const [selectedId, setSelectedId] = useState(requests[0]?.id ?? "")
  const [reportRef, setReportRef] = useState("")
  const request = requests.find((item) => item.id === selectedId) ?? requests[0]
  const generatedAt = useMemo(() => new Date().toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC", [])

  async function buildPdf() {
    if (!request) return
    const { jsPDF } = await import("jspdf")
    const pdf = new jsPDF({ unit: "mm", format: "a4" })
    const ref = reportId()
    setReportRef(ref)
    const width = pdf.internal.pageSize.getWidth()
    const height = pdf.internal.pageSize.getHeight()
    const blue = [35, 105, 220] as const
    const navy = [18, 38, 70] as const
    const pageDestinations: number[] = []
    const addPage = (title: string, pageNumber: number) => {
      if (pageNumber > 1) pdf.addPage()
      pageDestinations.push(pdf.getNumberOfPages())
      pdf.setFillColor(...navy); pdf.rect(0, 0, width, 25, "F")
      pdf.setTextColor(255, 255, 255); pdf.setFont("helvetica", "bold"); pdf.setFontSize(15); pdf.text("LETHEXA", 16, 12)
      pdf.setFont("helvetica", "normal"); pdf.setFontSize(8); pdf.text("PRIVACY OPERATIONS  /  EVIDENCE REPORT", 16, 19)
      pdf.setTextColor(...navy); pdf.setFont("helvetica", "bold"); pdf.setFontSize(18); pdf.text(title, 16, 39)
      pdf.setDrawColor(...blue); pdf.setLineWidth(1); pdf.line(16, 44, 35, 44)
      pdf.setTextColor(110, 120, 135); pdf.setFont("helvetica", "normal"); pdf.setFontSize(8)
      pdf.text(`${ref}  ·  ${request.id}`, 16, height - 10)
      pdf.text(`${pageNumber} / 6`, width - 16, height - 10, { align: "right" })
    }
    const label = (text: string, value: string, y: number) => {
      pdf.setTextColor(105, 115, 130); pdf.setFont("helvetica", "normal"); pdf.setFontSize(9); pdf.text(text.toUpperCase(), 16, y)
      pdf.setTextColor(30, 42, 60); pdf.setFont("helvetica", "bold"); pdf.setFontSize(11); pdf.text(value || "Not available", 16, y + 6)
    }
    const paragraph = (text: string, y: number, maxWidth = width - 32) => {
      pdf.setTextColor(55, 65, 80); pdf.setFont("helvetica", "normal"); pdf.setFontSize(10)
      const lines = pdf.splitTextToSize(text, maxWidth); pdf.text(lines, 16, y); return y + lines.length * 5 + 4
    }
    const table = (headers: string[], rows: string[][], y: number, widths: number[]) => {
      const x0 = 16; const rowHeight = 10
      pdf.setFillColor(235, 241, 250); pdf.rect(x0, y - 6, widths.reduce((a, b) => a + b, 0), rowHeight, "F")
      pdf.setFont("helvetica", "bold"); pdf.setFontSize(7); pdf.setTextColor(...navy)
      let x = x0; headers.forEach((h, i) => { pdf.text(h, x + 2, y); x += widths[i] })
      let cy = y + rowHeight
      rows.forEach((row, ri) => {
        if (cy > height - 22) return
        pdf.setFillColor(ri % 2 ? 255 : 249, ri % 2 ? 255 : 251, ri % 2 ? 255 : 254); pdf.rect(x0, cy - 6, widths.reduce((a, b) => a + b, 0), rowHeight, "F")
        pdf.setFont("helvetica", "normal"); pdf.setFontSize(7); pdf.setTextColor(45, 55, 70); x = x0
        row.forEach((cell, i) => { pdf.text(pdf.splitTextToSize(cell || "—", widths[i] - 4).slice(0, 2), x + 2, cy); x += widths[i] })
        cy += rowHeight
      })
      return cy + 5
    }

    addPage("Executive summary", 1)
    pdf.setTextColor(60, 70, 85); pdf.setFont("helvetica", "normal"); pdf.setFontSize(8)
    pdf.text("CONTENTS", 16, 54)
    sections.forEach((title, i) => {
      const column = i < 3 ? 0 : 1; const row = i % 3; const x = 16 + column * 88; const y = 64 + row * 10
      pdf.setTextColor(...blue); pdf.setFont("helvetica", "bold"); pdf.text(`${String(i + 1).padStart(2, "0")}`, x, y)
      pdf.setTextColor(...navy); pdf.setFont("helvetica", "normal"); pdf.text(title, x + 10, y)
      pdf.link(x, y - 5, 84, 9, { pageNumber: i + 1 })
      pdf.outline?.add(null, title, { pageNumber: i + 1 })
    })
    pdf.setTextColor(60, 70, 85); pdf.setFont("helvetica", "normal"); pdf.setFontSize(9)
    pdf.text("Synthetic demonstration evidence · No real personal data", 16, 103)
    label("Organisation", "Acme Corporation · Synthetic demo", 119)
    label("Report reference", ref, 140)
    label("DSR request", request.id, 161)
    label("Generated", generatedAt, 182)
    label("Request type / status", `${request.type} / ${request.status}`, 203)
    label("Identity verification", request.verification, 224)
    pdf.setFillColor(239, 245, 255); pdf.roundedRect(16, 241, width - 32, 38, 3, 3, "F")
    pdf.setTextColor(...navy); pdf.setFont("helvetica", "bold"); pdf.setFontSize(9); pdf.text("EXECUTIVE SUMMARY", 22, 250)
    paragraph(`This ${request.type.toLowerCase()} request is currently recorded as “${request.status}.” Identity verification is ${request.verification.toLowerCase()}. No deletion or fulfillment is asserted.`, 258, width - 44)

    addPage("Request details", 2)
    label("Request ID", request.id, 57); label("Masked subject identifier", request.identifier, 80)
    label("Submission date", request.date, 103); label("Request type", request.type, 126)
    label("Verification status", request.verification, 149); label("Workflow status", request.status, 172)
    pdf.setTextColor(90, 100, 115); pdf.setFontSize(9); pdf.text("Request reference is clickable and links to the source request in this report.", 16, 207)
    pdf.link(16, 198, 100, 13, { pageNumber: 1 })

    addPage("PII discovery results", 3)
    pdf.setTextColor(85, 95, 110); pdf.setFontSize(9); pdf.text("Synthetic demo findings · Not live source results", 16, 55)
    table(["SOURCE / DATABASE", "TABLE / COLUMN", "CATEGORY", "MATCHES", "CONF.", "REASON"], demoFindings.map(f => [`${f.source}\n${f.database}`, `${f.table}\n${f.column}`, f.category, String(f.records), f.confidence, f.reason]), 68, [39, 35, 22, 17, 16, 49])
    pdf.setTextColor(...navy); pdf.setFont("helvetica", "bold"); pdf.setFontSize(10); pdf.text("PII CATEGORY DISTRIBUTION", 16, 133)
    const categories = [{ name: "Contact", value: 38 }, { name: "Identity", value: 26 }, { name: "Financial", value: 17 }, { name: "Location", value: 19 }]
    categories.forEach((item, i) => {
      const y = 146 + i * 15; pdf.setFillColor(...blue); pdf.roundedRect(16, y - 4, item.value * 1.2, 5, 2, 2, "F")
      pdf.setFont("helvetica", "normal"); pdf.setFontSize(9); pdf.setTextColor(55, 65, 80); pdf.text(`${item.name}  ${item.value}%`, 165, y)
    })
    paragraph("Counts and category proportions are illustrative synthetic demo data; no request-specific live matches were supplied to the report generator.", 213)

    addPage("Approval and execution", 4)
    label("Verification result", request.verification, 58)
    label("Reviewer information", "Not available in supplied request data", 82)
    label("Approval status", request.status === "Completed" ? "Workflow marked completed; approval record unavailable" : "Not available; human approval evidence not supplied", 106)
    label("Dry-run deletion preview", request.type === "Delete" ? "Synthetic preview: 4 example records across 3 sources" : "Not applicable to access request", 130)
    label("Execution status", "No execution result supplied · No deletion asserted", 154)
    label("Human approval", "No approver identity or timestamp supplied", 178)
    paragraph("Deletion remains subject to explicit authorized human approval. This report does not perform or authorize a deletion.", 205)

    addPage("Audit trail", 5)
    pdf.setTextColor(70, 80, 95); pdf.setFontSize(10)
    paragraph("No request-specific audit events were provided to the report generator. Events are not inferred or fabricated.", 57)
    table(["TIME / ORDER", "AUDIT EVENT", "ACTOR", "RESULT"], [["Not available", "No source event supplied", "Not available", "Not available"]], 91, [32, 63, 44, 39])

    addPage("Evidence summary", 6)
    const summary = [
      ["Evidence reference", ref], ["Request reference", request.id], ["Audit event references", "None supplied"],
      ["Report generated", generatedAt], ["Data masking", "Confirmed: masked identifier only"],
      ["Outstanding actions", request.status === "Completed" ? "Review source completion evidence" : "Complete workflow and human review as applicable"],
      ["Limitations", "Synthetic finding examples; no live approvals, audit events or execution data"],
    ]
    table(["EVIDENCE ITEM", "DETAIL"], summary, 68, [47, 131])
    pdf.setProperties({ title: `LETHEXA Evidence Report ${request.id}`, subject: "DSR evidence report", author: "LETHEXA" })
    pdf.save(`lethexa-${request.id}-${ref}.pdf`)
  }

  function printReport() { window.print() }
  if (!request) return <div className="evidence-empty">No DSR requests are available to report.</div>

  return <>
    <div className="report-screen-only"><PageHeading eyebrow="PRIVACY OPERATIONS" title="Evidence reports" description="Preview structured evidence for a selected DSR. Reports distinguish supplied facts from synthetic demo data."/></div>
    <div className="evidence-builder">
      <section className="panel evidence-controls">
        <div className="panel-head"><div><h2>Report configuration</h2><p>Request status and masked subject are read from the selected request.</p></div><FileCheck2 size={20}/></div>
        <label className="form-label">Selected DSR request<select value={request.id} onChange={e => { setSelectedId(e.target.value); setReportRef("") }}>{requests.map(item => <option key={item.id} value={item.id}>{item.id} · {item.type} · {item.identifier}</option>)}</select></label>
        <div className="report-facts"><span>Request status<strong>{request.status}</strong></span><span>Verification<strong>{request.verification}</strong></span><span>Pages<strong>6 pages</strong></span></div>
        <div className="report-demo-note"><strong>Synthetic demo evidence</strong><span>Discovery examples are illustrative. No live source matches, approval details, audit events, or deletion execution are assumed.</span></div>
        <div className="report-actions"><button className="button button-primary" onClick={buildPdf}><Download size={15}/>Download PDF</button><button className="button button-outline" onClick={printReport}><Printer size={15}/>Print preview</button></div>
        {reportRef && <p className="report-success" role="status">PDF generated · Reference {reportRef}</p>}
      </section>
      <section className="panel report-outline" aria-labelledby="report-outline-title"><div className="panel-head"><div><h2 id="report-outline-title">Report preview</h2><p>{request.id} · {request.type} request · 6 pages</p></div><span className="report-page-count">6 PAGES</span></div>
        <div className="report-page-stack">{sections.map((title, i) => <article className="report-page-card" key={title}><div className="report-page-number">0{i + 1}</div><div><h3>{title}</h3><p>{i === 0 ? "Organisation, report reference, generation date, request status and executive summary." : i === 1 ? "Request ID, masked identifier, submission, type, verification and workflow status." : i === 2 ? "Demo source/table findings, categories, counts, confidence, reasons and distribution chart." : i === 3 ? "Approval evidence, reviewer details, dry-run preview and execution state." : i === 4 ? "Source-backed event timeline only; unavailable events remain explicitly unreported." : "Evidence references, masking confirmation, outstanding actions and limitations."}</p></div><Check aria-hidden="true"/></article>)}</div>
      </section>
    </div>
  </>
}

function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div></div>
}
