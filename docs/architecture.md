# System Architecture Document — KaamHour

## 1. System Overview

KaamHour is built as a modern, high-performance, mobile-first full-stack web application designed for real-time hyperlocal workforce coordination.

```
                          +------------------------------------------+
                          |        Client Tier (Next.js 15 App)      |
                          |  - Mobile-First Worker Experience (PWA)  |
                          |  - Responsive Vendor Command Center      |
                          |  - Admin Moderation & Audit Console      |
                          +--------------------+---------------------+
                                               |
                                    HTTPS / Next.js Server Actions / REST API
                                               |
                          +--------------------v---------------------+
                          |           Next.js Application Layer      |
                          |  - Authentication & RBAC Middleware      |
                          |  - Deterministic Matching Engine         |
                          |  - State Machine Lifecycle Engine        |
                          |  - Geolocation & Distance Calculation    |
                          |  - Gemini AI NLP Extractor & Summary     |
                          |  - Razorpay Webhook Verifier & Escrow    |
                          +--------------------+---------------------+
                                               |
         +------------------+------------------+------------------+------------------+
         |                  |                  |                  |                  |
+--------v-------+  +-------v--------+  +------v--------+  +------v--------+  +------v--------+
| Supabase Auth  |  | PostgreSQL DB  |  | Supabase S3   |  | Razorpay API  |  | Google Gemini |
| & RLS Policies |  | (Drizzle ORM)  |  | (Doc/Photo)   |  | (Payments)    |  | (NL Parsing)  |
+----------------+  +----------------+  +---------------+  +---------------+  +---------------+
```

---

## 2. Technology Stack & Architectural Decision Records (ADRs)

| Component | Selected Technology | Architectural Rationale |
| :--- | :--- | :--- |
| **Framework** | Next.js 15 (App Router, TypeScript) | Server Components for instant initial paint and SEO; Server Actions for atomic, type-safe backend operations; unified full-stack codebase. |
| **Styling** | Tailwind CSS + Custom Design System | Custom color tokens: Marine Blue (`#073B4C`), Bright Red (`#EF233C`), Lemon Yellow (`#F9E547`), Warm Off-White (`#F7F4EA`), Deep Charcoal (`#161616`). Clean, high-density, no generic SaaS purple gradients. |
| **Database & ORM** | PostgreSQL + Drizzle ORM | PostgreSQL provides strict ACID transactions, foreign keys, and geospatial calculations; Drizzle provides type-safe, lightweight, zero-overhead queries with migrations. |
| **Authentication** | Supabase Auth + JWT Cookies + RLS | Secure session tokens, native Row Level Security (RLS) enforcement on PostgreSQL tables, multi-role (Worker, Vendor, Admin) authorization. |
| **Maps & Geo** | Mapbox GL JS + Turf.js / Server Haversine | High precision distance calculations, interactive mobile-friendly shift map clustering, address geocoding with privacy-preserving approximate worker radii. |
| **Payments** | Razorpay (Node SDK + Webhooks) | Standard Indian payment gateway supporting UPI, Cards, NetBanking, and automated payout disbursement architecture with cryptographic HMAC-SHA256 webhook validation. |
| **AI Processing** | Google Gemini API (gemini-1.5-flash / gemini-2.0) | Structured JSON output mode for parsing unstructured natural language vendor shift requirements into typed schema fields; generating verifiable profile summaries. |
| **Monitoring** | Sentry Next.js SDK | Full-stack exception tracking, API route tracing, and performance monitoring without capturing PII or financial credentials. |

---

## 3. Core Engine Architectures

### 3.1 Deterministic Matching Engine
The Matching Engine evaluates candidate workers against a published shift requirement based on a weighted multi-factor scoring algorithm:

$$\text{Total Score} = 0.30 S_{\text{skill}} + 0.20 S_{\text{dist}} + 0.20 S_{\text{avail}} + 0.15 S_{\text{rel}} + 0.10 S_{\text{rating}} + 0.05 S_{\text{history}}$$

1. **Skill Compatibility ($S_{\text{skill}} \in [0, 100]$):**
   - $100\%$ if worker has all required verified skills.
   - Pro-rated based on matched required skills / total required skills.
2. **Distance Proximity ($S_{\text{dist}} \in [0, 100]$):**
   - $d \le 1.0\text{ km} \implies 100$
   - $1.0\text{ km} < d \le 15.0\text{ km} \implies 100 \times \left(1 - \frac{d - 1}{14}\right)$
   - $d > 15.0\text{ km} \implies 0$
3. **Availability ($S_{\text{avail}} \in \{0, 100\}$):**
   - Checks if worker has no overlapping confirmed booking or marked busy blocks for the target shift start/end timestamps.
4. **Reliability & On-Time ($S_{\text{rel}} \in [0, 100]$):**
   - Historical completion rate $\times 0.6 +$ on-time check-in rate $\times 0.4$. (Defaults to 85 for verified new workers).
5. **Rating ($S_{\text{rating}} \in [0, 100]$):**
   - $(\text{Average Rating} / 5.0) \times 100$. (Defaults to 80 for new workers).
6. **Similar History ($S_{\text{history}} \in [0, 100]$):**
   - Accumulated hours in the same category ($\min(100, \text{category\_hours} \times 5)$).

### 3.2 State Machine Lifecycle Engine
Every entity strictly transitions through legal state transformations enforced by PostgreSQL check constraints and backend service validators:

* **Work Post:** `draft` $\to$ `published` $\to$ `filled` / `in_progress` $\to$ `completed` (or `cancelled`)
* **Application:** `pending` $\to$ `accepted` / `rejected` / `withdrawn`
* **Booking:** `pending` $\to$ `confirmed` $\to$ `checked_in` $\to$ `in_progress` $\to$ `completed` (or `disputed` / `cancelled`)
* **Work Session:** `scheduled` $\to$ `checked_in` $\to$ `in_progress` $\to$ `completed` $\to$ `verified`

### 3.3 Dynamic Work Profile Engine
Whenever a `work_session` completes and both reviews are processed:
1. Transactionally update `workers.total_hours_worked` $+=$ `session.actual_hours`.
2. Increment `workers.shifts_completed`.
3. Recompute `on_time_rate` and `completion_rate`.
4. Upsert `worker_skills.accumulated_hours` for the specific skill tagged in the work post.
5. Recompute Bayesian weighted average rating.

---

## 4. Scalability & Extensibility Roadmap
* **Modular Category Taxonomy:** Skill and category structures use a parent-child hierarchical schema (`parent_category_id`), allowing zero-downtime additions of Retail, Warehousing, and Logistics verticals.
* **Pluggable Ranking Interface:** The ranking interface `IMatchingEngine` is abstracted, enabling a seamless transition from the V1 deterministic engine to a fine-tuned ML ranking model.
