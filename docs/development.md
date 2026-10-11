# Development Guide & Environment Setup — KaamHour

## 1. Prerequisites
* **Node.js:** v20.x or v22.x LTS (`node -v` $\ge 20.0.0$)
* **Package Manager:** `npm` ($\ge 10.x$)
* **PostgreSQL / Supabase:** Local PostgreSQL or cloud Supabase project
* **External API Keys (Optional for local dev with fallback mock simulators):**
  - Mapbox Access Token (for geocoding & map rendering)
  - Razorpay Key ID & Key Secret (Test mode `rzp_test_...`)
  - Google Gemini API Key (for natural language job extraction & profile summaries)

---

## 2. Quickstart Step-by-Step

### 2.1 Clone & Install Dependencies
```bash
npm install
```

### 2.2 Configure Environment Variables
Copy `.env.example` to `.env.local`:
```bash
cp .env.example .env.local
```
Fill in the values for PostgreSQL database URL, Supabase credentials, and API keys.

### 2.3 Run Database Migrations & Seed Realistic Data
```bash
npm run db:push
npm run db:seed
```

### 2.4 Start Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 3. Seed Accounts for Local Testing

| Role | Email | Password | Description |
| :--- | :--- | :--- | :--- |
| **Worker (Top Rated)** | `rahul.patil@example.com` | `Password123!` | 326 hrs, 47 shifts, 4.79 rating, Kitchen & Packaging specialist |
| **Worker (Cleaning Pro)** | `sunita.devi@example.com` | `Password123!` | 210 hrs, 31 shifts, 4.90 rating, Deep cleaning & Dishwashing |
| **Worker (New Worker)** | `arun.kumar@example.com` | `Password123!` | 12 hrs, 2 shifts, 5.00 rating, Waiter & banquet support |
| **Vendor (Restaurant)** | `shree.snacks@example.com` | `Password123!` | Shree Snacks (Indiranagar), 42 shifts posted |
| **Vendor (Cloud Kitchen)**| `royal.kitchen@example.com` | `Password123!` | Royal Cloud Kitchen (Koramangala), High volume evening shifts |
| **Admin** | `admin@kaamhour.internal` | `AdminPass123!` | Full platform administration, KYC & dispute moderation |

---

## 4. Running Test Suites
```bash
npm run test          # Unit tests (Matching engine, Dynamic Profile, Payment math)
npm run test:e2e      # End-to-end user workflow simulations
```
