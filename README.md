# 🛡️ GateKeeper: Smart Student Asset Protection

[![Live App](https://img.shields.io/badge/LIVE_APP-OPEN_STREAMLIT-00c853?style=for-the-badge&logo=streamlit)](https://your-app-url.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Security-first campus device verification platform built by an AI Engineer + Pharmacy student to address real laptop theft incidents with operational-grade auditability.

---

## 🛡️ Crisis Context

Campus exits were relying on paper logs and visual checks that were easy to bypass, hard to audit, and impossible to investigate after theft.  
GateKeeper converts the gate workflow into a digital, time-aware, logged verification process.

---

## 📱 Live App Link

- Production URL: [https://keepstudent.streamlit.app](https://your-app-url.streamlit.app)
- Gate QR should point to this single URL (static QR, student-scans-gate model).

---

## ⚙️ System Architecture (Student-Scans-Gate)

![alt text](<Auth Session Management Flow-2026-04-26-220154.png>)

---

## 📊 Old System vs GateKeeper

| Capability | Old Manual System | SentryID Pro |
|---|---|---|
| Gate verification | Paper-based, subjective | Digital pass with live clock |
| Identity binding | Weak (name/ID only) | Auth user + registered serial + photo |
| Theft response | Reactive | Real-time stolen kill-switch |
| Auditability | Manual notebook logs | Structured `exit_logs` in Supabase |
| Incident forensics | Slow, incomplete | Time filters, serial search, CSV export |
| Session UX | Re-login friction | Persistent cookie sessions (30 days) |

---

## 🛡️ Core Pro Features

- **Automated Audit Logging:** Every successful green pass render writes an `exit_logs` record (name, serial, IP, timestamp).
- **Session-Persistent Access:** Cookie-backed auth keeps students logged in up to 30 days on the same device/browser.
- **Admin Forensics Console:** Live feed, date/time windows, serial history search, CSV export.
- **Mobile-first Pass Screen:** High-contrast UI, large identity fields, massive serial number, live ticking time.
- **Admin-Controlled Onboarding:** No public sign-up; all accounts and registrations are managed centrally.

---

## 📊 The Audit Trail Feature

When a student reaches a gate and the pass is rendered successfully:

1. The app validates session + student registration.
2. The app ensures an active pass window (5 minutes).
3. A silent entry is inserted into `exit_logs`:
   - `student_id`
   - `student_name`
   - `laptop_serial`
   - `ip_address`
   - `timestamp`
4. Duplicate logs from page refresh are prevented in-session using `st.session_state`.

This narrows theft investigation scope quickly by answering:
- Who exited with this serial?
- At what exact time?
- From which network edge/IP path?

---

## 📊 Administrative Dashboard (Forensics)

Protected admin-only panel includes:

- **Live Feed:** Most recent 50 exit events.
- **Time Filter:** Query between precise start/end date-time values.
- **Serial Search:** Track complete movement history of a target device serial.
- **Export:** Download filtered evidence as CSV for security office workflows.

---

## 📱 Mobile Installation (PWA-Style)

SentryID is designed for phone-first operation at gate checkpoints. Install the app as a home-screen shortcut for near-native launch behavior and better session continuity.

### Android (Chrome)
1. Open the live app URL.
2. Tap browser menu (⋮).
3. Tap **Add to Home screen**.
4. Confirm install.

### iPhone (Safari)
1. Open the live app URL.
2. Tap **Share**.
3. Tap **Add to Home Screen**.
4. Confirm.

### Why this matters
- Faster launch at gate.
- Fewer session disruptions.
- Better reliability for persistent login state.

---

## 🛡️ Security Countermeasures

### Identity Swap Protection
- Pass UI displays the registered laptop serial in very large format.
- Guard checks on-device serial sticker against app serial before allowing exit.
- Prevents "wrong laptop, right student account" abuse pattern.

### Stolen Kill-Switch
- `is_stolen = true` forces immediate flashing-red alert state.
- Alarm view overrides normal pass rendering.
- Enables immediate on-site intervention.

### Data Integrity Controls
- RLS policies enforce role-based data access.
- DB trigger prevents students from mutating protected identity fields.
- Registration is admin-restricted.

---

## 📊 Developer Forensics Notes (IP/Browser Fingerprinting)

Current forensic payload includes:
- IP-oriented capture from request headers (`x-forwarded-for` / `x-real-ip` fallback).
- User, device serial, and exact timestamp for each verified exit event.

Recommended next hardening iteration:
- Persist user-agent and normalized device fingerprint in `exit_logs`.
- Add anomaly alerts (same account exiting from distant IP regions within short windows).

---

## ⚙️ Setup

### 1) Supabase
1. Create project in [Supabase](https://supabase.com).
2. Open SQL Editor.
3. Run [`supabase_schema.sql`](./supabase_schema.sql) after replacing `admin@campus.edu` with your real admin email.

### 2) Environment Variables
Create `.env`:

```env
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
ADMIN_EMAIL=admin@campus.edu
APP_BASE_URL=http://localhost:8501
PASS_SIGNING_SECRET=long-random-secret
```

### 3) Run Locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **Backend/Data/Auth:** Supabase (PostgreSQL + Auth + Storage)
- **Language:** Python 3.9+
- **Session Persistence:** `extra-streamlit-components` cookies
- **Live UI Updates:** `streamlit-autorefresh`

---

## 📄 License

Distributed under the MIT License. See `LICENSE`.

---

Built for real campus safety operations by an AI Engineer and Pharmacy student.  
Security is not a feature here; it is the product.