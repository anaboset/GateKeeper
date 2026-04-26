# 🛡️ GateKeeper: Smart Campus Asset Protection

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📌 The Problem
In the past week alone, multiple high-value asset (PCs) have been stolen from students on campus. The current security infrastructure relies on manual paper logs and physical ID cards that are:
1. **Easy to Forge:** Guards cannot verify if a serial number on a paper belongs to the person carrying the device.
2. **High Friction:** Manual checks create long queues, leading guards to become "lazy" and skip verification.
3. **Reactive, Not Proactive:** Once a device is past the gate, there is no way to flag it as stolen in real-time.

## 🚀 The Solution: GateKeeper
**GateKeeper** is a zero-cost, cloud-based verification ecosystem that shifts the power of security to the student’s smartphone. It replaces easily faked paper IDs with a **dynamic, time-sensitive Digital Exit Pass**.

### Key Features
* **Admin-Controlled Registration:** Only the admin account can register/update student devices.
* **Scan-to-Exit:** Students generate a signed 5-minute pass link and guards open `/verify` directly.
* **Visual Verification:** Displays the student's photo and the device's **Serial Number** in high-contrast, large fonts for easy guard inspection.
* **Anti-Fraud Logic:** Includes a live ticking clock with strict 5-minute pass expiry.
* **The Kill-Switch:** Students can mark a device as "Stolen" in the app. If that device is scanned at any gate, the screen flashes a high-visibility alarm to alert the guard immediately.

![Stolen Status](https://img.shields.io/badge/STOLEN_ALARM-ACTIVE-red?style=for-the-badge&logo=opsgenie)

---

## 🛠️ Technical Stack
* **Frontend:** [Streamlit](https://streamlit.io/) (Mobile-responsive UI)
* **Backend/Database:** [Supabase](https://supabase.com/) (PostgreSQL + Auth)
* **Deployment:** Streamlit Community Cloud
* **Language:** Python 3.9+

---

## 📋 System Architecture
1.  **Registration:** Admin registers student laptop details and profile photo.
2.  **The Gate Process:**
    * Student logs in, generates a 5-minute signed pass URL, and shows/uses it as QR.
    * Guard opens the dedicated `pages/verify.py` route with tokenized query params.
    * App validates token + pass expiry + stolen status and displays the **Verification Pass**.
3.  **The Guard Check:** The guard performs a 3-point check:
    * Does the photo match the student?
    * Does the Serial Number on the screen match the laptop sticker?
    * Is the live clock moving and pass not expired?

---

## ⚙️ Installation & Setup

### 1. Database Setup (Supabase)
The database schema is pre-configured to handle user profiles, device registration, and theft-flagging logic.
* Go to your [Supabase Dashboard](https://supabase.com).
* Open the **SQL Editor**.
* Copy the contents of [`supabase_schema.sql`](./supabase_schema.sql) and paste them into a new query.
* Run the query to initialize the tables and security policies.

### 2. Local Development
```bash
# Clone the repository
git clone https://github.com/your-username/SentryID.git
cd SentryID

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run streamlit_app.py
```

### 3. Environment Variables
Create a `.env` file or add to Streamlit Secrets:
```env
SUPABASE_URL = "https://<project>.supabase.co"
SUPABASE_ANON_KEY = "<anon-key>"
SUPABASE_SERVICE_ROLE_KEY = "<service-role-key>"
ADMIN_EMAIL = "admin@campus.edu"
APP_BASE_URL = "http://localhost:8501"
PASS_SIGNING_SECRET = "long-random-secret"
```

---

## 🛡️ Security Pro-Tips Implemented
* **No Public Signup:** Accounts are pre-created by admin in Supabase Auth.
* **Time-To-Live (TTL):** Passes expire automatically after 5 minutes.
* **Signed Verify URL:** Guard page token is HMAC-signed and time-bound.
* **DB Update Guard:** Students are blocked at trigger level from editing profile/device identity fields.
* **High-Visibility Stolen State:** CSS flashing red alarm if device is flagged stolen.

---

## 🤝 Roadmap
- [ ] Integration with Campus WiFi MAC address logs.
- [ ] Telegram Bot alerts for instant "Stolen" flagging.
- [ ] AI-based face matching between profile photo and live camera check.

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

---
**Created with 💻 by an Engineering & Pharmacy Student to keep our campus safe.**