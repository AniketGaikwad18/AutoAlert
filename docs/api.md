# API Architecture Specification — KaamHour

## 1. API Design Principles
* **Standard:** Next.js 15 REST Route Handlers (`/app/api/.../route.ts`) and Type-Safe Server Actions.
* **Authentication:** Supabase Auth Bearer JWT / Cookie session verification on every non-public endpoint.
* **Validation:** All payloads validated with Zod schemas; rejects with 400 Bad Request and detailed field error maps.
* **Error Handling:** Unified JSON error envelope `{ "success": false, "error": { "code": "RESOURCE_NOT_FOUND", "message": "..." } }`.
* **Rate Limiting:** IP and user-based token bucket rate limiting on sensitive routes (auth, work posting, applying).

---

## 2. API Endpoints Catalog

### 2.1 Authentication & Profile APIs
* `GET /api/auth/me` — Returns the authenticated user, role, and associated worker/vendor profile.
* `POST /api/auth/register` — Registers a user with role (`worker` | `vendor`), creating initial records.
* `PATCH /api/workers/me` — Updates worker bio, location coordinates, preferences, availability.
* `PATCH /api/vendors/me` — Updates vendor company profile, tax/FSSAI details, and default location.

### 2.2 Work Posts & Marketplace Discovery
* `GET /api/work-posts` — List published shifts with query filters:
  - `lat`, `lng`, `radius_km` (Geolocation filtering)
  - `category_id`, `skills` (Taxonomy filtering)
  - `min_wage`, `max_wage` (Budget filtering)
  - `date`, `start_time`, `end_time` (Time window filtering)
  - `sort_by` (`recommended` | `closest` | `highest_pay` | `soonest`)
* `POST /api/work-posts` — Create a new work requirement (Vendor only).
* `GET /api/work-posts/[id]` — Detailed shift information, requirements, location, and applicant count.
* `POST /api/work-posts/ai-parse` — Gemini AI Natural Language parser (extracts structured shift parameters from free text).
* `PATCH /api/work-posts/[id]/status` — Update shift status (`published`, `cancelled`, `closed`).

### 2.3 Applications & Matching Engine
* `POST /api/work-posts/[id]/apply` — Worker applies for an open shift (runs match scoring and checks availability conflicts).
* `GET /api/work-posts/[id]/matches` — Vendor retrieves ranked candidate list with match scores and explainable breakdown.
* `GET /api/work-posts/[id]/applications` — Vendor lists applications for a specific post.
* `PATCH /api/applications/[id]` — Vendor accepts or rejects an applicant (Accepting creates a locked `booking`).

### 2.4 Bookings & Work Session Lifecycle
* `GET /api/bookings` — List user's active/past bookings (filtered by role).
* `GET /api/bookings/[id]` — Detailed booking view including location, wage, and current session state.
* `POST /api/work-sessions/[id]/check-in` — Worker check-in with GPS coordinates verification ($<500\text{m}$ radius validation).
* `POST /api/work-sessions/[id]/start` — Vendor confirms worker presence; session moves to `in_progress`.
* `POST /api/work-sessions/[id]/complete` — Shift end recording; validates timestamps and computes actual verified hours.

### 2.5 Dynamic Work Profiles & Reviews
* `GET /api/workers/[id]/profile` — Public/Vendor view of worker Dynamic Profile (calculated verified metrics).
* `POST /api/reviews` — Submit bilateral post-shift review (`rating` 1-5, comment).
* `GET /api/reviews/worker/[id]` — Paginated verified employer reviews for a worker.

### 2.6 Payments & Financial Transactions
* `POST /api/payments/create-order` — Generates Razorpay Order ID for verified shift invoice.
* `POST /api/payments/verify` — Validates Razorpay signature and marks booking invoice paid.
* `POST /api/payments/webhook` — Handles asynchronous Razorpay webhook events (`payment.captured`, `payment.failed`).
* `GET /api/vendor/spending` — Vendor financial breakdown (completed hours, platform fees, historical receipts).
* `GET /api/worker/earnings` — Worker payout ledger (pending, processing, credited amounts).

### 2.7 Admin & Compliance APIs
* `GET /api/admin/dashboard` — Platform macro metrics (active shifts, completion rate, GMV, disputes).
* `GET /api/admin/disputes` — List open worker-vendor disputes.
* `POST /api/admin/disputes/[id]/resolve` — Admin resolution action (refund vs payout allocation).
* `PATCH /api/admin/users/[id]/status` — Suspend or reinstate user account.
* `GET /api/admin/audit-logs` — Immutable audit trail of platform administrative actions.

---

## 3. Standard Request / Response Formats

### 3.1 Error Response Payload
```json
{
  "success": false,
  "error": {
    "code": "DOUBLE_BOOKING_CONFLICT",
    "message": "Worker already has a confirmed booking overlapping with this shift time window (7:00 PM - 11:00 PM)."
  }
}
```

### 3.2 Matching Engine Result Payload
```json
{
  "worker_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "match_score": 94,
  "match_reasons": [
    { "factor": "skills", "score": 98, "description": "Matched all 2 required skills (Kitchen Assistance, Cleaning)" },
    { "factor": "distance", "score": 95, "description": "1.4 km away from Indiranagar Kitchen" },
    { "factor": "availability", "score": 100, "description": "Available for full 7:00 PM - 11:00 PM window" },
    { "factor": "reliability", "score": 96, "description": "94% on-time check-in, 97% completion rate" },
    { "factor": "rating", "score": 94, "description": "4.7 average rating across 47 completed shifts" },
    { "factor": "experience", "score": 90, "description": "86 verified hours in Kitchen Assistance" }
  ]
}
```
