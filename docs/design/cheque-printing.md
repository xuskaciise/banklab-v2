# Cheque printing & handover — design (Backlog)

Status: **Backlog** (not in Phase 1). Builds on 1.10 Cheques (chequebook series,
paid once, stop payment) and the PDF tooling from 1.12 Reports.

## How real banks do it (what students should learn)
1. Customer requests a chequebook (Current account).
2. Core system reserves a **series** (e.g. 100001–100025) for the account and
   produces a **print order** (account no, name, branch, series).
3. A **security printer** prints the books (security paper, watermark, MICR
   line) — branch systems never print real cheques.
4. Books arrive at the branch and are kept in safe custody.
5. Customer collects the book and signs an **acknowledgment**; CSO
   **activates** the series. Only active leaves can be paid.
6. Teller pays a presented cheque after checking series, status (unused / not
   stopped), signature and funds.

## BankLab flow
Chequebook status: `ordered` → `printed` → `delivered` (customer signed) →
`active`. Only `active` leaves can be paid (1.10 rule extends to this).

| Step | Who | Screen action |
|---|---|---|
| Request + reserve series | CSO | existing "Issue chequebook" → status `ordered` |
| Print order / print | CSO (simulates printer) | "Print chequebook" → PDF, status `printed` |
| Hand over + activate | CSO | "Deliver & activate" (acknowledgment checkbox) → `active` |
| Pay cheque | Teller | existing cheque withdrawal; optional on-screen cheque view |

No journal entries (non-posting, like transactions.md §F). Every step is
audited and bank-scoped; permission `cheque.issue` (CSO).

## Training chequebook PDF (option A — chosen first)
- A4, 3 leaves per page, plain paper; one leaf per cheque number in the series.
- Leaf layout (landscape strip ~ 20 × 9 cm, light-blue background with a
  pale line pattern; layout follows the classic Indian bank cheque format the
  user supplied as reference — **layout only**, never another bank's name,
  logo or codes):

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [logo] {Lab bank name}     {Branch name}           Valid for 3 months    │
│                            {Branch address}        ┌─┬─┬─┬─┬─┬─┬─┬─┐   │
│                            Branch code {code}      │D│D│M│M│Y│Y│Y│Y│   │
│                                                    └─┴─┴─┴─┴─┴─┴─┴─┘   │
│ PAY ____________________________________________________ OR BEARER     │
│ AMOUNT (in words) ________________________________   ┌──────────────┐  │
│ __________________________________________________   │ {CCY}        │  │
│                                                      └──────────────┘  │
│ ┌A/c No──────────────────┐                                              │
│ │ {account number}       │  VALID FOR {CCY} {limit} & UNDER             │
│ └────────────────────────┘                                              │
│ {Account name}                                    ____________________ │
│ Prefix {series prefix}                            Authorised signatory │
│ {Product} CHEQUE — payable at all branches of {Lab bank}  Please sign above │
│                                                                          │
│      ⑈{cheque no}⑈   {branch code}⑆   {account no}⑈   {txn code}        │
│      (cheque no)      (bank/branch)    (account)       (type)            │
└──────────────────────────────────────────────────────────────────────────┘
          diagonal watermark: TRAINING – NOT NEGOTIABLE
```

- Fields (all from the system; only the layout is fixed):
  - Header: lab bank name + optional logo (session's bank, from setup),
    branch name, address, branch code.
  - Date boxes `D D M M Y Y Y Y` (8 boxes, blank — filled by the customer).
  - "PAY ____ OR BEARER", "AMOUNT (in words)" two lines, amount-in-figures
    box prefixed with the account currency (USD / SOS).
  - A/c No box with the account number; account name under it.
  - "VALID FOR {CCY} {limit} & UNDER" — optional, from product settings.
  - Signature line "Please sign above" (blank).
  - Bottom code line (normal font, MICR-style look):
    `⑈cheque no⑈  branch code⑆  account no⑈  txn code` — e.g. txn code
    `10` savings, `11` current (from product).
  - Watermark "TRAINING – NOT NEGOTIABLE" + small "BankLab" footer.
- Diagonal watermark on every leaf: **"TRAINING – NOT NEGOTIABLE"** plus
  "BankLab" footer, so a print can never pass as a real cheque.
- Stub (counterfoil) on the left of each leaf for the customer's record.
- Rendered server-side with the same PDF engine as receipts/reports.

## On-screen cheque (option B — later, optional)
- Student "customer" fills a cheque image on screen (date, payee, amount,
  words); teller sees the same image when paying and must match amount in
  words vs figures. Mismatch = teaching case for rejection.

## Open questions
- Should a teller reject when amount in words ≠ figures (needs option B)?
- Bounced/cancelled cheques stay in Backlog (separate item).
