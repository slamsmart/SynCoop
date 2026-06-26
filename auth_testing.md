# Auth-Gated App Testing Playbook (Emergent Google Auth)

## Step 1: Create Test User & Session
```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  role: 'ADMIN',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```
curl -X GET "$URL/api/auth/me" -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Step 3: Browser Testing
Set cookie `session_token` (httpOnly, secure, sameSite None) then navigate.

## Demo Quick-Access (no Google needed)
POST /api/auth/demo with body {"role": "ADMIN"|"NELAYAN"|"PETUGAS_LAPANG"|"PETUGAS_DINAS"}
Returns a session_token for the seeded demo user of that role.

## Checklist
- users have user_id (custom), all queries use {"_id": 0}
- session.user_id matches user.user_id
- /api/auth/me returns user (not 401)
