# Theme & Design Tokens — BankLab V2

Source: the user's "SIU Bank Admin System — Color Scheme & Design Tokens"
spec (derived from the SIU brand, adapted for a banking back-office UI).
All UI must use these tokens — never hard-code hex values in components.
Light theme only for now.

## 1. Brand
| Token | Hex | Use |
|-------|-----|-----|
| `bank-navy` | `#0F2942` | Sidebar, top bar, large headings, security notices |
| `bank-primary` | `#1E3A8A` | Primary CTA / submit buttons, active tabs |
| `bank-accent` | `#0284C7` | Chart lines, active indicators, focus rings |
| `bank-sky-light` | `#E0F2FE` | Badge background, secondary buttons |

## 2. Financial status
| Token | Hex | Use |
|-------|-----|-----|
| `fin-success` | `#059669` | Deposits / credits in, account opened, completed |
| `fin-success-dark` | `#047857` | Success text inside tables |
| `fin-success-bg` | `#ECFDF5` | "Completed / Success" badge background |
| `fin-pending` | `#D97706` | Pending approvals, awaiting supervisor, warnings |
| `fin-pending-bg` | `#FEF3C7` | Warning / pending background |
| `fin-danger` | `#DC2626` | Withdrawals / debits out, closed accounts, errors |
| `fin-danger-bg` | `#FEE2E2` | "Failed / Rejected" background |

## 3. Surfaces
| Token | Hex | Use |
|-------|-----|-----|
| `surface` | `#F8FAFC` | App background |
| `card` | `#FFFFFF` | Cards, tables |
| `border` | `#E2E8F0` | Table cell borders, dividers |
| `hover` | `#F1F5F9` | Table row hover |

## 4. Text
| Token | Hex | Use |
|-------|-----|-----|
| `text-strong` | `#0F172A` | H1/H2, balances, amounts |
| `text-body` | `#334155` | Body and customer data |
| `text-muted` | `#64748B` | Timestamps, account numbers, metadata |

## 5. Banking UI rules
- Amounts: right-aligned, tabular numerals, always with currency (`USD 1,250.00`, `SOS 50,000.00`).
- Direction colour: credit/in = `fin-success`, debit/out = `fin-danger`; never colour alone — also show `+`/`−` or Dr/Cr.
- Status badges: `posted` → success, `pending_approval` → pending, `rejected`/`reversed` → danger, `closed` → muted.
- Dr/Cr learning panel: Dr column `bank-primary`, Cr column `bank-accent`, on `bank-sky-light`.
- Focus ring: 2px `bank-accent` on every interactive element (keyboard use at the teller counter).

## 6. Implementation (Tailwind v4 + shadcn/ui)
Define tokens once in `frontend/app/globals.css`:

```css
@theme {
  --color-bank-navy: #0F2942;
  --color-bank-primary: #1E3A8A;
  --color-bank-accent: #0284C7;
  --color-bank-sky-light: #E0F2FE;
  --color-fin-success: #059669;
  --color-fin-success-dark: #047857;
  --color-fin-success-bg: #ECFDF5;
  --color-fin-pending: #D97706;
  --color-fin-pending-bg: #FEF3C7;
  --color-fin-danger: #DC2626;
  --color-fin-danger-bg: #FEE2E2;
  --color-surface: #F8FAFC;
  --color-card: #FFFFFF;
  --color-border: #E2E8F0;
  --color-hover: #F1F5F9;
  --color-text-strong: #0F172A;
  --color-text-body: #334155;
  --color-text-muted: #64748B;
}
```

Map shadcn's semantic variables onto them: `--primary` → bank-primary,
`--ring` → bank-accent, `--destructive` → fin-danger, `--background` → surface,
`--card` → card, `--border`/`--input` → border, `--foreground` → text-body,
`--muted-foreground` → text-muted, `--sidebar` → bank-navy.
