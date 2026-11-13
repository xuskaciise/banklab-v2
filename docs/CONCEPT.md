# BankLab V2 — Fikradda Nidaamka (System Concept)

> Ujeeddo: BankLab waa **shaybaar waxbarasho** (training lab) oo ardayda kulliyadda
> Banking ay ku bartaan sida bangi dhab ah u shaqeeyo. Ma aha nidaam bangi oo
> shaqo dhab ah. Dokumentigan wuxuu sharxayaa (1) waxa hadda jira, (2) meelaha
> fikradda bangiga ay ka khaldan tahay ama ka maqan tahay, (3) sida V2 casri ah
> loo dhisi lahaa, iyo (4) diyaargarowga features-ka mustaqbalka.

---

## 1. Waxa nidaamka hadda jira (V1)

| Qayb | Waxa ay qabato |
|------|----------------|
| **Branch** | Laamaha bangiga (magac, cinwaan, maamule, `limit_amount`) |
| **Account** | Macmiil + akoon isku dhafan: magac, jinsi, telefoon, dokumenti (ID), sawir, saxiix, next-of-kin, branch. Lambarka waa `SAL0001…` |
| **Stock (Vault)** | Khasnadda lacagta caddaanka ah. Maamule ayaa leh |
| **Teller (`taller`)** | Sanduuqa lacagta ee shaqaale kasta. Lacag ayuu ka helaa Vault-ka, wuuna u celiyaa. Waa la furi karaa/xiri karaa (Open/Close) |
| **Deposit** | Macmiilku lacag ayuu dhigaa → akoonkiisu wuu kordhaa, sanduuqa teller-kana wuu kordhaa |
| **Withdraw** | Lacag la bixiyo → hubin: sanduuqa teller-ka iyo haraaga akoonka ma ku filan yihiin |
| **Cheque** | Lambarro jeeg ah ayaa akoon loo diiwaangeliyaa; lacag ayaa jeeg lagu bixiyaa |
| **Transfer** | Akoon → akoon kale |
| **Statement / Reports** | Bayaanka akoonka, warbixinnada teller-ka iyo macaamilladiisa |
| **Employee** | Xogta shaqaalaha (CV, dokumenti) |
| **Users & Authority** | Isticmaalayaal (Admin/User), menu iyo awoodo (category → link → action) loo qoondeeyo user kasta |
| **Clean System** | Admin ayaa xogta tirtira si fasal cusub uu uga bilaabo (reset) |

**Socodka lacagta ee V1:** `Vault → Teller → Macmiil` iyo dhanka kale `Macmiil → Teller → Vault`.
Fikradda aasaasiga ah waa sax, waana meesha ugu fiican ee wax laga dhiso.

---

## 2. Meelaha fikradda bangiga ay ka khaldan tahay (V1)

### 2.1 Xisaabaadka (Accounting) — dhibaatada ugu weyn
- **Ma jiro General Ledger (GL) iyo double-entry.** Bangi dhab ah, macaamil kasta
  wuxuu sameeyaa ugu yaraan laba qayd (Debit/Credit) oo isku dheelli ah. Tusaale,
  deposit: *Dr Cash (Teller) / Cr Customer Deposits (liability)*. V1 wuxuu
  si gooni ah u cusbooneysiiyaa haraaga teller-ka iyo akoonka, wax isku xira ma jiraan.
  Ardaydu sidaas darteed ma arkaan **Trial Balance** ama **Balance Sheet**.
- **Transfer-ku wuxuu taabanayaa sanduuqa teller-ka** (+ iyo −). Transfer waa
  macaamil aan lacag caddaan ahayn (non-cash); sanduuqa waa inuusan taaban.
- Lacagta waxaa lagu kaydiyaa `varchar` ama `decimal(10,0)`, taas oo luminaysa senti-yada.
- Haraaga waxaa lagu xisaabiyaa SUM marka la akhrinayo, mana jiro *running balance*
  ama *available vs ledger balance*.

### 2.2 Macmiilka iyo akoonka
- **Macmiil = akoon** (isku table). Bangiga dhabta ah: **Customer (CIF)** hal mar ayaa
  la diiwaangeliyaa → wuxuu yeelan karaa akoonno badan (savings, current,
  joint account, akoon shirkadeed).
- Nooca akoonka waa qoraal xor ah. Ma jiraan **Products** leh xeerar sida
  min balance, faa'iido/profit, kharash (fees) iyo xadka lacag bixinta.
- Ma jiraan **xaalado akoon**: Pending → Active → Dormant → Frozen → Closed.
  Akoonka waa la **tirtiri** karaa, taas oo bangi aan la samayn.
- KYC waa xog la keydiyo oo kaliya. Ma jiro **KYC verification / approval**.

### 2.3 Teller iyo Vault
- Open/Close waa calaamad oo kaliya. Ma jiro **Teller Session** leh opening
  balance, **cash count (denominations)**, *over/short* iyo **End-of-Day**.
- Vault-ka si cad ugama xirna branch-ka, mana jiro **dual control**
  (laba qof oo ogolaada lacag Vault-ka ka baxda).
- `branch.limit_amount` ayaa jira, laakiin **xadka teller-ka iyo approval** ma shaqeeyo.

### 2.4 Jeegagga
- Jeeg kasta si gooni ah ayaa loo diiwaangeliyaa. Ma jiro **Chequebook issuance**
  (buug leh taxane lambarro ah) iyo **xaaladda jeegga** (issued / paid / stopped / bounced).
  Jeeg la isticmaalay mar kale ayaa la isticmaali karaa.
- Bixinta jeegga waxay si adag ugu xiran tahay `Taller0001`.

### 2.5 Hubinta iyo kontaroolka
- Ma jiro **maker–checker** (qof sameeya iyo qof kale oo ansixiya) iyo **reversal**
  (macaamil khaldan oo si sax ah loo celiyo, lana tirtirin).
- Ma jiro **audit trail** (yaa sameeyay, goorma, maxaa isbeddelay).
- Ma jiro **transaction reference / receipt** iyo **business date** (taariikhda
  shaqada bangiga, oo ka duwan saacadda kombiyuutarka).

### 2.6 Waxbarashada
- Nidaamku ma garanayo **fasal, arday ama macallin**. Dhammaan ardaydu waxay
  wadaagaan hal database, "Clean System"-kuna wax walba ayuu tirtiraa.
- Ma jiraan **layli (exercises), xaalado (scenarios)** iyo **qiimayn**.

---

## 3. Fikradda V2 — BankLab casri ah

### 3.1 Mabaadi'da
1. **Ledger-first:** macaamil kasta wuxuu sameeyaa journal entry double-entry ah.
   Haraaga waxaa laga soo saaraa ledger-ka.
2. **Waxbarasho ayaa ugu horraysa:** shaashad kasta waxay tusin kartaa
   *"Maxaa dhacay xisaab ahaan?"* (qaydka Dr/Cr, isbeddelka GL).
3. **Sandbox fasal kasta:** fasal/koox kasta wuxuu leeyahay bangi u gaar ah
   (*Lab Instance*), kaas oo dib loo dejin karo iyadoo kuwa kale aan la taaban.
4. **Xeerarka bangiga dhabta ah:** xaalado, xadad, ansixin, reversal,
   end-of-day, iyo audit.
5. **Doorar (roles)** u dhigma bangi dhab ah iyo macallin.

### 3.2 Doorarka (Roles)
| Door | Waxa uu sameeyo |
|------|-----------------|
| **Instructor (Macallin)** | Abuura fasal/Lab, ku daraa arday, qoondeeya doorar, abuura scenarios, arka natiijooyinka, reset gareeya |
| **Student** | Lab-ka gudahiisa wuxuu qaataa door bangi (hoos ka eeg), wuuna isbeddeli karaa (role rotation) |
| Teller | Deposit, withdraw, cheque, cash count |
| Customer Service / CSO | Diiwaangelinta macmiilka, furitaanka akoonka, KYC |
| Branch Manager / Supervisor | Ansixinta (checker), xadadka, EOD-ka laanta, Vault |
| Back Office / Operations | Transfers, clearing, reversals |
| Accountant | GL, Trial Balance, warbixinnada maaliyadda |
| Compliance / AML | Alerts, KYC review, xannibaadda akoonnada |
| *(Mustaqbal)* Customer | Portal internet/mobile banking |

### 3.3 Qaybaha (Modules) — MVP

**A. Lab Management (cusub)**
- Institutions → Classes → Lab Instances → Students
- Reset/clone Lab, **seed data** (macaamiil iyo lacag diyaarsan si layliga loo bilaabo)
- Business Date: macallinka ayaa "maalinta" hore u wadi kara (si interest/EOD loo baro)

**B. Customer (CIF) & KYC**
- Shakhsi / shirkad, dokumentiyo, sawir, saxiix, next-of-kin
- KYC status: Draft → Submitted → Verified/Rejected (maker–checker)
- Risk rating (Low/Medium/High), oo loo baahan doono AML-ka

**C. Products & Accounts**
- Product catalog: Savings, Current, Fixed/Term Deposit, (islaamiga) Wadiah/Mudarabah
  — xeerar: min balance, fees, profit/interest rate, lacag-bixin xad leh
- Akoon: hal macmiil → akoonno badan; **joint accounts**; mandates (yaa saxiixi kara)
- Xaalado: Pending → Active → Dormant → Frozen → Closed (mana jiro delete)
- Ledger balance vs **available balance** (holds/blocks)

**D. Teller & Cash Management**
- Vault branch kasta leh, dual control
- **Teller Session**: open (opening cash) → macaamil → close (cash count by
  denomination, over/short, supervisor sign-off)
- Cash transfer: Vault ⇄ Teller, Teller ⇄ Teller
- Xadka teller-ka: lacag ka badan xadka → waxaa ansixiya supervisor-ka

**E. Transactions**
- Cash deposit/withdrawal, internal transfer (non-cash), cheque
- Transaction reference, **receipt/voucher** la daabici karo, narration
- **Reversal** (mana jiro tirtirid) iyo maker–checker
- Amount-in-words si toos ah ayaa loo sameeyaa (kuma qorayo gacanta)

**F. Cheques**
- Chequebook request → issue (taxane lambarro ah) → cheque status
- Stop-payment, bounced cheque (iyo kharashkiisa)
- *(Mustaqbal)* inter-bank cheque clearing simulation

**G. General Ledger & Accounting**
- Chart of Accounts (Assets / Liabilities / Equity / Income / Expense)
- Journal entries si toos ah ugu imaanaya macaamil kasta
- Trial Balance, Balance Sheet, Income Statement
- **"Learning panel":** macaamil kasta wuxuu muujiyaa qaydkiisa Dr/Cr

**H. End of Day (EOD)**
- Xiritaanka teller-yada → xiritaanka laanta → accruals (faa'iido/kharash) →
  business date-ka cusub. Ardaydu waxay bartaan habka xiritaanka bangiga.

**I. Reports**
- Account statement (PDF), teller cash report, branch daily report,
  GL reports, audit log

**J. Security & Audit**
- Login ammaan ah (hashed passwords), RBAC + permission matrix (V1 wuxuu leeyahay
  fikrad wanaagsan oo la sii wadi karo), audit trail dhammaystiran

### 3.4 Waxbarasho gaar ah (waxa BankLab ka dhigaya "Lab")
- **Scenarios / Exercises:** macallinka ayaa sameeya hawl, tusaale *"Fur akoon
  joint ah, dhig $500, ka bixi $120 jeeg, kadibna xir teller-ka. Haraaga sanduuqa
  waa inuu noqdaa X."* Nidaamku si toos ah ayuu u hubiyaa natiijada.
- **Inject events:** macallinka ayaa soo geliya dhibaato (jeeg been abuur ah,
  macmiil KYC-giisu dhacay, lacag la waayay) si ardaydu u xalliyaan.
- **Grading & activity log:** arday kasta waxa uu sameeyay iyo khaladaadkiisa.
- **Guided mode vs Exam mode:** caawimaad iyo sharraxaad, ama imtixaan aan caawimaad lahayn.
- **Afaf:** Ingiriisi + Soomaali (i18n).

---

## 4. Diyaargarowga features-ka mustaqbalka

Si loogu daro mustaqbalka iyadoo aan dib loo dhisin, MVP-ga waa in lagu dhisaa:
- **Ledger engine** guud: feature kasta oo cusub (loans, cards, mobile money)
  wuxuu sameeyaa journal entries.
- **Product engine** xeerarkiisu yihiin configuration, oo aan ku qornayn code-ka.
- **Event/Audit log**: macaamil kasta waa event, taas oo u fududaynaysa AML,
  notifications iyo analytics.
- **API-first**: si loogu daro portal macaamiil iyo mobile app.
- **Multi-tenant (Lab instance)** laga bilaabo maalinta koowaad.

**Features Phase 3+:**
- **Loans / Financing:** codsi → credit appraisal → ansixin → disbursement →
  jadwalka bixinta → overdue/provisioning (ama Murabaha/Mudarabah)
- **Interest/Profit & Fees engine** (accrual maalinle, posting bille)
- **Mobile money / Cards simulation** (ATM, POS, wallets sida EVC/Zaad oo la simuleeyay)
- **Internet/Mobile Banking portal** (arday ayaa noqda "macmiil")
- **Inter-bank:** clearing, RTGS/SWIFT simulation
- **FX / Currency exchange** (USD/SOS)
- **AML/CFT monitoring:** rules, alerts, sanctions screening simulation
- **Dashboards & analytics** macallinka iyo maamulka

---

## 5. Khariidadda shaqada (Roadmap) ee la soo jeediyay

| Phase | Waxa ku jira |
|-------|--------------|
| **0. Design** | Xaqiijinta fikraddan, Chart of Accounts, doorarka, wireframes |
| **1. Core (MVP)** | Lab mgmt, Auth/RBAC, Branch, CIF+KYC, Products, Accounts, GL engine, Teller+Vault sessions, Deposit/Withdraw/Transfer, Reversal, Receipts, Statements, Audit |
| **2. Operations** | Cheques (chequebook), maker–checker xadad leh, EOD + business date, Trial Balance/Balance Sheet, Scenarios + grading |
| **3. Products** | Interest/fees engine, Term deposits, Loans/Financing, FX |
| **4. Channels** | Customer portal, mobile money/cards simulation, AML module |

---

## 6. Go'aannada la gaaray (2026-11-06)

| # | Su'aal | Go'aan |
|---|--------|--------|
| 1 | Nooca bangiga | **Labadaba**: Conventional + Islamic. Product kasta wuxuu leeyahay `banking_model` (interest iyo profit-sharing) |
| 2 | Lacagta | **USD + SOS**, iyo FX/sarrif. Akoon kasta hal currency ayuu leeyahay; GL-ka waa multi-currency |
| 3 | Kulliyadaha | **Hal kulliyad**, fasallo badan. Schema-da waxaa ku jira `institution_id` si mustaqbalka loo ballaariyo |
| 4 | Doorarka ardayda | **Role rotation**: arday wuxuu Lab-ka gudahiisa ku qaadan karaa doorar kala duwan |
| 5 | V1 | **Dib-u-dhis buuxa**: technology iyo fikrad cusub. V1 ma laha xog loo wareejinayo (V2 wuxuu ka bilaabmayaa seed data), laakiin **features-ka V1 oo dhan waa inay V2 ku jiraan** (V1 = baseline), kadibna kor ayaa wax loogu darayaa |
| 6 | Technology | **Next.js (frontend) + Django 5 / Django Ninja (backend API) + PostgreSQL** — go'aan 2026-11-07 (wuxuu beddelay Laravel + MySQL) |

### Qaybta 1 — Lab & Waxbarasho (go'aan)
- Lab: **labadaba** — macallinku marka uu fasal abuurayo ayuu doortaa: hal bangi fasalka oo dhan, ama bangi koox kasta.
- Doorka ardayga: **macallinka** ayaa qoondeeya kana beddela.
- Ardayda gelinta: **gacan (mid mid)** + **Excel/CSV import**.
- MVP (Phase 1): **Activity log** (macallinku wuxuu arkaa waxa arday kastaa sameeyay) + **Business date** (macallinka ayaa maalinta hore u wada).
  Layli + hubin toos ah iyo dhibco/imtixaan → **Phase 2** (waxay u baahan yihiin in macaamilka iyo GL-ku marka hore dhammaystirmaan).
- **Visibility (muuqaalka xogta)** — macallinku wuxuu u dejin karaa Lab kasta (ama arday gaar ah):
  - **"Kaliya waxaan sameeyay"**: ardaygu wuxuu arkaa oo kaliya macaamiisha, akoonnada iyo macaamilka uu isagu abuuray.
  - **"Bangiga oo dhan"**: ardaygu wuxuu arkaa dhammaan shaqada bangiga (Lab-ka) ka socota, oo uu xaddidayo doorkiisa/awoodihiisa.
  - Macallinku wuu beddeli karaa wakhti kasta (tusaale: imtixaan → "kaliya waxaan sameeyay"; layli kooxeed → "bangiga oo dhan").
  - Macallinka iyo warbixinnada maamulka (EOD, GL) waxay mar walba arkaan Lab-ka oo dhan.
  - Tusaale: 30 arday oo dhammaantood Teller ah → macallinku arday kasta wuxuu u dooran karaa
    "shaqadiisa oo kaliya" ama "shaqada ardayda kale oo dhan" (hal mar fasalka oo dhan, ama arday-arday).
- **Lab Sessions (xiisado) — xallinta dhibaatada V1:** V1 xiisad cusub kasta xogta hore waa la tirtiri jiray.
  V2: macallinku wuxuu fasalka u furaa **session cusub** (tusaale "Semester 1 – 2027").
  - Session cusub = bangi nadiif ah (seed data + Chart of Accounts), ardaydu xog hore ma arkaan.
  - Session-nadii hore **lama tirtiro** — waa la xiraa (archived, read-only); macallinku wuu eegi karaa,
    warbixin ka soo saari karaa, ama dib u furi karaa.
  - Xogta oo dhan (macaamiil, akoonno, macaamil, GL) waxay ku xiran tahay `session_id`, sidaas ayaa xogtu u kala go'antahay.
  - "Clean System" ee V1 → waxaa beddelaya "Open new session"; tirtirid ma jirto.
  - **Session = hal xiisad (lecture/lab period).** Tusaale: fasalka "Banking – Semester 5" wuxuu semester-ka
    qaataa 5 xiisadood; 3 ka mid ah waa layli **Teller/Cashier oo kaliya**. Xiisad kasta macallinku wuxuu u furaa
    **session cusub → data cusub**; ardaydu ma arkaan shaqadii xiisaddii hore. Xiisaddii hore waa la xiraa (archive), lama tirtiro.
  - Marka session la furayo macallinku wuxuu doortaa: **magac** (tusaale "Xiisad 3 – Teller"), **doorarka la oggol yahay**
    (tusaale Teller kaliya), **visibility**, **seed data** (macaamiil + lacag diyaarsan), iyo **Dr/Cr panel** shid/dami.
    Settings-kan waxaa loo kaydin karaa **template** si xiisadaha soo socda hal riix loogu furo.
  - Qaab-dhismeedka: `Class (Banking – Semester 5) → Sessions (Xiisad 1..n, Exam) → Students → doorar → xog`.

### Exam Session (cusub — MVP)
Exam-ku waa session sida kuwa kale (data cusub, ka go'an xiisadaha kale), laakiin leh features imtixaan:
- **Wakhti:** saacadda bilowga iyo dhammaadka / muddo (tusaale 60 daqiiqo); marka wakhtigu dhammaado shaqada waa la xiraa (read-only).
- **Hawlo (tasks):** macallinku wuxuu qoraa hawlaha (tusaale "Fur akoon Savings, dhig $500, bixi jeeg $120, xir sanduuqa");
  arday kasta wuxuu helaa **xog u gaar ah** (macaamiil/lacag) si aan la iska koobiyeyn.
- **Xaddidaad:** visibility = "kaliya waxaan sameeyay" (qasab), Dr/Cr panel = dami, caawimaad ma jirto.
- **Hubin toos ah + dhibco:** nidaamku wuxuu barbar dhigaa natiijada ardayga iyo jawaabta saxda ah
  (haraaga akoonka, sanduuqa teller-ka, qaydka GL); macallinku dhibcaha wuu beddeli karaa (manual adjust).
- **Natiijooyin:** liiska ardayda iyo dhibcahooda, faahfaahinta khaladaadka, export PDF/Excel.
- **Activity log:** wax kasta oo ardaygu sameeyay iyo wakhtigiisa.

### Qaybta 2 — Branch, Vault & Teller (go'aan)
- Furitaanka teller-ka: Vault → teller opening cash, **supervisor ayaa ansixiya**.
- Xiritaanka: **cash count nooc-nooc (denominations)** USD iyo SOS; nidaamku wuxuu xisaabiyaa over/short.
- Xadka teller-ka: lacag ka badan xadka → **supervisor ayaa ansixiya** (maker–checker).
- Vault: **dual control** — Vault custodian + Manager.

### Qaybta 3 — Macmiil (CIF) & KYC (go'aan)
- Noocyada macaamiisha: **Shakhsi, Shirkad/Ganacsi, Joint, Hay'ad/NGO** (shirkad/hay'ad → signatories + mandate).
- Furitaanka akoonka: **isla markiiba** (CSO) — ansixin KYC ma jirto MVP-ga.
- **KYC buuxa ka hor akoon (go'aan 2026-11-08):** akoon lama furi karo ilaa macmiilku leeyahay: address; qof kasta oo saxiixa — sawir (profile), saxiix sawir ah, iyo ugu yaraan hal ID document oo scan/sawir leh; individual/joint — owner kasta next of kin. Server-ka ayaa xisaabiya (`kyc_complete`, `kyc_missing`); 1.7 ayaa dhaqangelinaya.
- Dokumentiyada: **National ID, Passport, Warqad xaafadeed**.
- Risk rating: **mustaqbalka** (AML phase).

### Qaybta 4 — Products & Accounts (go'aan)
- Conventional MVP: **Savings, Current, Fixed Deposit**.
- Islamic MVP: **Mudarabah Savings, Mudarabah Term** (Wadiah → mustaqbalka).
- Lambarka akoonka: **taxane fudud** (tusaale 1000123).
- Xaaladaha: **fudud — Active / Closed** (Dormant/Frozen/holds → mustaqbalka).
- **Cusbooneysiin:** Fixed Deposit + Mudarabah Savings/Term → **Phase 4** (waxay u baahan yihiin faa'iido engine).
  MVP products = **Savings + Current** oo kaliya; product model-ku wuxuu hore ugu diyaar yahay `banking_model` (conventional/islamic).

### Luqadda
- Shaashadaha: **English oo kaliya**.

### Qaybta 5 — Macaamilka (go'aan)
- Reversal: **teller-ka ayaa toos u celiya** (qayd lid ah; lama tirtiro, audit-ka ayaa diiwaangeliya).
- Rasiid: **PDF la daabici karo** (reference no., lacagta oo qoraal ah, saxiix).
- Qofka dhigaya/qaadanaya: **magac + ID + telefoon**.
- Fees: **mustaqbalka**.

### Qaybta 6 — Jeegagga (go'aan)
- **Buug jeeg** (request → issue, taxane lambarro ah).
- Akoonnada: **Current + Savings**.
- Xaaladaha MVP: **Paid (hal mar)** + **Stop payment** (Bounced/Cancelled → mustaqbalka).

### Qaybta 7 — Xisaabaadka / GL (go'aan)
- Learning panel (Dr/Cr): **macallinka ayaa shida/damiya** Lab kasta (guided vs exam).
- Warbixinnada MVP: **Trial Balance, Balance Sheet, Income Statement, GL Ledger**.
- End-of-Day: **ardayga doorka Manager-ka leh** ayaa sameeya.
- Chart of Accounts: **template diyaarsan + macallinku wuu beddeli karaa**.

### Qaybta 8 — Sarrifka / FX (go'aan)
- **Mustaqbalka** (MVP: akoon kasta lacagtiisa ayaa lagu shaqeeyaa; GL-ku wuxuu diyaar u yahay multi-currency).
- Marka la dhiso: rate-ka **Manager (arday)** ayaa maalin kasta dejiya; **buy + sell rate** (spread = dakhli);
  **cross-currency transfer waa la oggol yahay** (rate-ka maalintaas).

### Qaybta 9 — Users, Doorar & Audit (go'aan)
- Doorarka MVP: **Teller, CSO, Supervisor/Manager, Vault Custodian, Accountant** (+ Instructor, Admin).
- Permissions: **default door kasta + macallinku wuu beddeli karaa** (permission matrix).
- Login ardayga: **username = student ID**, password-ka koowaad = **4-ta lambar ee ugu dambeeya telefoonkiisa**; login-ka koowaad wuxuu ku qasbaa inuu beddelo. Password policy **fudud**. (Go'aan 2026-11-07 wuxuu hoos ku sixay: macallinku ardayda wuu reset gareyn karaa.)
- **Go'aan 2026-11-07 (sixitaan) — Ardaygu password buu leeyahay:** ardaygu wuxuu galaa **Student ID + password**; password-ka koowaad = 4-ta lambar ee ugu dambeeya telefoonkiisa, `must_change_password=True`, waana qasbanaa inuu beddelo (sida staff; server-ka ayaa fuliya). Staff (instructor/admin) waxay isticmaalaan `/staff/login` (username + password), isla xeerka password-ka koowaad. Reset: **Admin** wuu reset gareyn karaa qof kasta (arday iyo instructor) isla machadka; **Instructor** wuxuu reset gareyn karaa **ardayga** oo keliya (1.3 ayaa ku xadidi doonta ardayda fasalladiisa), ma reset gareyn karo staff. Reset = password-ka koowaad + `must_change_password=True`, audit. Endpoints: `POST /api/auth/student-login` {student_id, password}, `POST /api/auth/staff-login` (`/api/auth/login` waa laga saaray); isticmaal-isku-darka (student door / staff door) wuxuu soo celiyaa isla 401 "Invalid credentials". Throttle iyo audit (`auth.login` / `auth.login_failed`) waa isku mid.
- Audit log: **macallinka (wax walba) + Manager (Lab-kiisa)**.

### Qaybta 10 — Warbixinnada (go'aan)
- Operational MVP: **Account statement, Teller cash report, Branch daily report, Transaction journal**.
- Dashboards: **Macallin, Manager, Teller**.
- Export: **PDF + Excel**.

### Qaybta 11 — Mustaqbalka (go'aan)
- Dhammaan afarta waa la rabaa, sidan ayay isugu xigaan: **Layli + dhibco → Loans/Murabaha → FX + Fees + Faa'iido → Mobile/Internet banking**.
- Islamic financing: **Murabaha, Musharakah, Qard Hasan** (Ijara → maya hadda).

### Roadmap-ka la cusbooneysiiyay (go'aannada kor ku xusan)
| Phase | Waxa ku jira |
|-------|--------------|
| **0. Design** | ERD, Chart of Accounts, transaction catalog (Dr/Cr), permission matrix, liiska shaashadaha |
| **1. MVP** | Lab (fasal/koox, arday gacan + Excel, doorar, reset, business date, activity log, visibility: "kaliya waxaan sameeyay" / "bangiga oo dhan") · Auth (student ID + password, first = last 4 phone digits; staff username + password) · Branch/Vault (dual control)/Teller session (supervisor open, denomination close, xad + ansixin) · CIF (4 nooc) + KYC docs · Products (Savings, Current) · Accounts (Active/Closed) · Deposit/Withdraw/Transfer (isla currency) · Reversal · PDF receipt · Chequebook (Paid, Stop) · GL + Dr/Cr panel · EOD · Warbixinnada (TB, BS, IS, GL ledger, statement, teller, branch, journal; PDF+Excel) · Dashboards · Audit |
| **1 (sii)** | **Sessions (xiisad kasta data cusub, templates, archive)** + **Exam Session** (wakhti, hawlo, xog gaar ah, hubin toos ah, dhibco, natiijooyin) — MVP-ga ayuu ku jiraa (go'aan 2026-11-06) |
| **2** | Layli/scenarios (guided practice) + inject events |
| **3** | Loans + Murabaha, Musharakah, Qard Hasan |
| **4** | FX (buy/sell, cross-currency), Fees, Interest/Profit-sharing engine, Fixed Deposit, Mudarabah Savings/Term |
| **5** | Mobile/Internet banking portal, mobile money simulation |
| Later | KYC approval, risk rating/AML, Dormant/Frozen, Wadiah, Bounced/Cancelled cheques |

### V1 → V2 baseline (feature parity)
Branch · Customer/Account (KYC, sawir, saxiix, next-of-kin) · Vault (stock) ·
Teller (open/close, Vault ⇄ Teller) · Deposit · Withdraw · Cheque withdraw ·
Transfer · Account statement · Teller reports · Employee · Users + permission
matrix (category → link → action) · Clean System (V2: Lab reset).
