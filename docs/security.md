# Security & Threat Model Specification — KaamHour

## 1. Security Architecture Principles

* **Defense in Depth:** Validation and authorization enforced at Database (PostgreSQL RLS & constraints), API Routing (Middleware & Server Actions), and UI (Role-based views).
* **Least Privilege:** Public users cannot read unmasked worker locations or contact details; vendors only see worker profiles within context of applications; workers cannot modify verification counters.
* **Zero Trust Payments:** Client-side payment callbacks are strictly treated as advisory. Payments are verified via cryptographic HMAC signatures (`crypto.createHmac('sha256', secret)`) and webhook idempotency tables.

---

## 2. Row Level Security (RLS) Policies

### 2.1 Worker Privacy & Geolocation
* Exact worker residential addresses (`workers.exact_address`) are restricted to the worker themselves and platform admins.
* Public/marketplace endpoints only return `approx_latitude` and `approx_longitude` (perturbed by a pseudo-random jitter $\pm 250\text{m}$) to prevent stalking or off-platform poaching before a booking is confirmed.

### 2.2 Dynamic Profile Tamper Resistance
* The `total_hours_worked`, `shifts_completed`, `on_time_rate`, `completion_rate`, and `average_rating` columns on `workers` table are immutable by workers.
* RLS policy and PostgreSQL triggers restrict updates to these columns strictly to internal database service functions executed upon shift review finalization.

### 2.3 Row Level Access Control Matrix

| Table | Worker Permission | Vendor Permission | Admin Permission |
| :--- | :--- | :--- | :--- |
| `users` | Read/Update Self | Read/Update Self | Read/Update All |
| `workers` | Read Any, Update Self Profile | Read Verified Profiles of Applicants | Full Access |
| `vendors` | Read Public Profile & Locations | Read/Update Self Business | Full Access |
| `work_posts` | Read Published Posts | Full CRUD on Own Posts | Full Access |
| `applications` | Create Own, Read Own | Read/Update for Own Posts | Full Access |
| `bookings` | Read Own | Read Own | Full Access |
| `work_sessions` | Check-in / Start Own | Verify & Complete Own Shifts | Full Access |
| `payments` | Read Own Payout Records | Read Own Payment Orders | Full Access |
| `audit_logs` | No Access | No Access | Read All |

---

## 3. Webhook & Signature Verification

### Razorpay Webhook Authentication
```typescript
import crypto from 'crypto';

export function verifyRazorpayWebhook(
  rawBody: string,
  signature: string,
  secret: string
): boolean {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(rawBody)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(expectedSignature),
    Buffer.from(signature)
  );
}
```

---

## 4. Input Sanitization & Rate Limiting
* All text inputs (bios, job descriptions, review notes) are sanitized against XSS using DOMPurify / sanitize-html.
* API endpoints implement in-memory token bucket rate limiters:
  - Shift applications: 30 requests/minute per worker.
  - Natural Language Job Parsing: 10 requests/minute per vendor.
  - Payment Order Creation: 15 requests/minute per vendor.
