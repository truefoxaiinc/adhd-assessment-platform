# Frontend Integration: Guest Subscriptions

This document is the implementation contract for Flutter integration with the
deployed Attention Minder backend.

## 1. Supported products

- `attentionminder.monthly`
- `attentionminder.quarterly`

Always display the title, price, and currency returned by StoreKit or Google
Play. Do not hardcode prices in the application.

## 2. Token model

The application can operate in three states:

| State | API credential | Meaning |
|---|---|---|
| Anonymous | No authorization header | Can list content and open unlocked free content |
| Guest subscriber | `Authorization: Bearer <guestEntitlementToken>` | Can access active subscription content and save progress |
| Registered user | `Authorization: Bearer <accessToken>` | Normal account access |

Persist the guest token in secure device storage using the key
`guestEntitlementToken`. Never put both a guest token and a registered-user JWT
in the same request.

The backend also accepts `X-Entitlement-Token`, but Bearer authorization is the
preferred client integration.

## 3. API response envelope

Most endpoints use this envelope:

```json
{
  "status": true,
  "status_code": 200,
  "message": "Success",
  "data": {},
  "errors": {}
}
```

Use the HTTP status as the authoritative result. Do not grant access solely
because a cached client flag says the user is subscribed.

## 4. Complete endpoint list

### List learning content

```http
GET /api/content/v1/contents?section=management&page=1&page_size=20
```

Authentication is optional. Supported query parameters:

- `section`: required; `management` or `assessment`
- `day`: optional positive integer
- `content_type`: optional; for example `video`, `article`, `file`, or `activity`
- `page` and `page_size`: optional pagination values

Important response fields:

```json
{
  "data": {
    "section": "management",
    "current_day": 1,
    "total_days": 30,
    "has_active_subscription": false,
    "results": [
      {
        "id": 12,
        "day": 1,
        "content_type": "video",
        "is_locked": false,
        "locked_reason": null,
        "is_completed": false
      },
      {
        "id": 18,
        "day": 2,
        "is_locked": true,
        "locked_reason": "An active subscription is required for Day 2 and later."
      }
    ]
  }
}
```

Daily progression and subscription access are separate. An active subscription
does not automatically unlock future days before the previous-day/time rule is
satisfied.

### Legacy file list

```http
GET /api/filehandler/v1/filehandler/list-files?is_management=true
```

Authentication is optional. Locked entries return `is_locked: true` and their
`file` value is `null`, preventing premium file URLs from being exposed.

### Content detail

```http
GET /api/content/v1/contents/{contentId}
```

Authentication is optional for unlocked free content. Send a guest or user
Bearer token for premium content. Locked content returns `403`.

### Save legacy learning progress

```http
POST /api/filehandler/v1/filehandler/update-learning-progress/
Authorization: Bearer <guest-or-user-token>
Content-Type: application/json

{"file_id": 12}
```

This endpoint requires either a guest entitlement token or registered-user JWT.
The referenced lesson must be unlocked.

### Learning-content progress and questions

All of these require a guest entitlement token or registered-user JWT:

```text
POST /api/content/v1/contents/{contentId}/submit
GET  /api/content/v1/contents/{contentId}/attempt-history
GET  /api/content/v1/attempts/{attemptId}/questions
POST /api/content/v1/attempts/{attemptId}/submit
```

## 5. Verify a purchase

```http
POST /api/payments/v1/payments/verify-in-app-purchase/
Content-Type: application/json
```

Do not send an Authorization header for a new guest purchase.

### iOS request

```json
{
  "platform": "ios",
  "product_id": "attentionminder.monthly",
  "transaction_id": "APPLE_TRANSACTION_ID",
  "verification_data": "SIGNED_TRANSACTION_OR_RECEIPT_DATA",
  "verification_source": "app_store",
  "is_restore": false
}
```

Use the verified StoreKit transaction ID and signed transaction/receipt supplied
by the in-app-purchase library. Do not generate these values locally.

### Android request

```json
{
  "platform": "android",
  "product_id": "attentionminder.monthly",
  "purchase_id": "GPA.ORDER_ID",
  "purchase_token": "GOOGLE_PLAY_PURCHASE_TOKEN",
  "verification_source": "google_play",
  "is_restore": false
}
```

`verification_data` may be used instead of `purchase_token`, but
`purchase_token` is preferred on Android.

### Guest success response

```json
{
  "status": true,
  "status_code": 200,
  "message": "Purchase verified",
  "data": {
    "verified": true,
    "subscription_status": "active",
    "platform": "ios",
    "product_id": "attentionminder.monthly",
    "expires_at": "2026-12-01T12:00:00Z",
    "is_guest": true,
    "entitlement_token": "OPAQUE_SERVER_GENERATED_TOKEN"
  },
  "errors": {}
}
```

Save `data.entitlement_token` to secure storage immediately. Only call the
store's `completePurchase()` after backend verification succeeds.

For an already logged-in purchase, send the registered-user JWT. The response
does not contain a guest entitlement token and `is_guest` is false.

## 6. Check entitlement

```http
GET /api/payments/v1/payments/entitlement/
Authorization: Bearer <guestEntitlementToken-or-user-JWT>
```

Grant premium access only when the response contains both:

```json
{
  "verified": true,
  "subscription_status": "active"
}
```

`grace_period` can also be returned as an active backend entitlement. Treat the
backend `verified` boolean as authoritative.

## 7. Restore purchases

Restore must be available while logged out. Query restored purchases through
StoreKit/Google Play and send each applicable transaction through the same
verification endpoint with:

```json
{"is_restore": true}
```

Do not call `purchase-account-identifiers` for a guest restore. A successful
restore returns a fresh guest entitlement token. Replace any previously stored
guest token, refresh entitlement, refresh content, and then complete the store
transaction if required by the Flutter purchase library.

## 8. Optional account linking

After registration or login, retain the guest token temporarily and call:

```http
POST /api/payments/v1/payments/link-guest-entitlement/
Authorization: Bearer <registered-user-accessToken>
Content-Type: application/json

{"entitlement_token": "GUEST_ENTITLEMENT_TOKEN"}
```

Success:

```json
{
  "status": true,
  "data": {
    "linked": true,
    "verified": true,
    "subscription_status": "active",
    "expires_at": "2026-12-01T12:00:00Z",
    "is_guest": false
  }
}
```

Delete `guestEntitlementToken` only after this request succeeds. On failure,
keep it so the user can retry. Never silently link a guest purchase to a newly
logged-in account; show a confirmation first.

`GET /api/payments/v1/payments/purchase-account-identifiers/` is only for an
already authenticated account purchase. It must never block guest purchase or
restore.

## 9. Flutter purchase-state handling

Use one purchase-stream subscription for the application's lifetime and avoid
registering duplicate listeners.

| Store state | Client action |
|---|---|
| `pending` | Keep loading state and explain that approval is pending |
| `canceled` | Clear loading state and close the purchase flow |
| `error` | Clear loading state, show a safe error, complete only if the plugin requires it |
| `purchased` | Verify with backend, store token, check entitlement, then complete purchase |
| `restored` | Verify with `is_restore: true`, replace token, check entitlement, then complete |

Recommended successful sequence:

```text
Store purchased/restored
  -> POST verify-in-app-purchase
  -> securely save entitlement_token
  -> GET entitlement
  -> confirm verified == true
  -> completePurchase
  -> refresh content APIs with guest Bearer token
```

If backend verification fails, do not unlock content and do not mark the user as
subscribed locally.

## 10. App startup and navigation

At startup:

1. If a registered-user JWT exists, validate/load the registered session.
2. Otherwise, if `guestEntitlementToken` exists, call the entitlement endpoint.
3. If it is active, enter the program as a guest subscriber.
4. If it is invalid or inactive, remove it only after an authoritative response
   and continue as an anonymous/free user.
5. Load the content list with the selected credential, or no credential for an
   anonymous user.

“Continue without an account” must navigate directly to the program and must not
open `LoginScreen`. Login and registration remain optional actions.

## 11. API error handling

| HTTP status | Meaning | Frontend behavior |
|---|---|---|
| `400` | Invalid request fields | Correct payload; show validation message if useful |
| `401` | Missing/invalid/expired token | Clear invalid credential and return to anonymous or login state |
| `403` | Entitlement exists but is inactive, or content/day is locked | Show paywall or locked-day explanation |
| `409` | Guest entitlement is already linked to another account | Do not retry with the same account; show support guidance |
| `422` | Invalid, manipulated, unsupported, expired, or revoked store evidence | Do not unlock; show purchase verification failure |
| `500` | Store verification/configuration failure | Keep transaction recoverable and offer retry/restore |

Never display raw receipt, purchase token, entitlement token, or backend stack
details in logs or user-visible errors.

## 12. Client service responsibilities

The frontend integration should have these logical services:

- `SecureTokenStore`: read/write/delete `guestEntitlementToken` and user tokens.
- `ApiAuthInterceptor`: attach the user JWT, otherwise guest token, otherwise no header.
- `PurchaseService`: own product loading, purchase stream, purchase, restore, and completion.
- `PaymentRepository`: verify purchase, check entitlement, and link guest entitlement.
- `ContentRepository`: list/detail/progress calls using the shared auth interceptor.
- `SessionController`: resolve registered, guest-subscriber, or anonymous state at startup.

Do not make each repository independently choose tokens. A single interceptor or
credential provider prevents inconsistent authorization.

## 13. End-to-end acceptance checklist

- [ ] Fresh install contains no user JWT and no guest token.
- [ ] Continue without account opens the program, not LoginScreen.
- [ ] Day 1 is visible and unlocked; later premium days are locked.
- [ ] Monthly and quarterly localized store products load.
- [ ] Guest purchase does not call `purchase-account-identifiers`.
- [ ] Native store confirmation appears without app registration.
- [ ] Purchased transaction is verified by the backend.
- [ ] Returned guest token is stored securely.
- [ ] Entitlement check returns `verified: true`.
- [ ] `completePurchase()` runs after successful verification.
- [ ] Content refresh uses the guest Bearer token.
- [ ] App restart restores guest access from the stored token.
- [ ] Expired/revoked entitlement cannot access premium content.
- [ ] Restore works while logged out and replaces the guest token.
- [ ] Restore works after reinstall/on another device through store history.
- [ ] Guest progress survives restart.
- [ ] Login/register offers guest-entitlement linking.
- [ ] Successful linking removes the local guest token.
- [ ] Guest progress and entitlement appear on the registered account.
- [ ] Linking an entitlement owned by another account handles `409` correctly.
- [ ] Real Apple Sandbox and Google license-tester flows pass before release.

## 14. Backend deployment state

Guest verification, entitlement authentication, free-content listing, protected
premium content, guest progress, restore, and account linking are implemented on
the backend. Migration `payments.0003_guest_entitlements` has been applied on
AWS. The Flutter team must still implement and validate this contract against
Apple Sandbox/TestFlight and Google Play test tracks.
