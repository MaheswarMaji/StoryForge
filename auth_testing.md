# StoryForge — Auth-Gated App Testing Playbook (Emergent Google Auth)

## How auth works here
- Login is Google-only via Emergent Auth: `https://auth.emergentagent.com/?redirect=<origin>/dashboard`
- After consent, frontend lands on `/dashboard#session_id=...`, AuthCallback POSTs `{session_id}` to `/api/auth/session`
- Backend exchanges it at `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data`, stores user + session (7 days), sets httpOnly cookie `session_token` (secure, samesite=none)
- ALL `/api/*` routes require auth (cookie OR `Authorization: Bearer <session_token>`) EXCEPT:
  `/api`, `/api/`, `/api/auth/*`, `/api/oauth/callback`, `/api/media-health`, and the static `/api/media/*` mount

## Step 1: Create a test session directly in Mongo
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('SESSION_TOKEN=' + sessionToken);
"

## Step 2: Test backend API (use the external preview URL, not localhost)
# Unauthenticated -> 401
curl -s -o /dev/null -w "%{http_code}" https://<preview-url>/api/stories
# Authenticated -> 200
curl -s https://<preview-url>/api/auth/me -H "Authorization: Bearer SESSION_TOKEN"
curl -s https://<preview-url>/api/stories -H "Authorization: Bearer SESSION_TOKEN"
curl -s https://<preview-url>/api/settings/instagram -H "Authorization: Bearer SESSION_TOKEN"

## Step 3: Browser testing
await page.context.add_cookies([{
    "name": "session_token",
    "value": "SESSION_TOKEN",
    "domain": "<preview-host-without-scheme>",
    "path": "/",
    "httpOnly": true,
    "secure": true,
    "sameSite": "None"
}]);
await page.goto("https://<preview-url>/dashboard");  // must NOT bounce to /login

## Checklist
- `/api/auth/me` returns user data with user_id/email/name/picture
- Unauthenticated /api/* JSON calls return 401 (not data)
- With cookie/bearer: dashboard loads, stories list loads
- `/login` shows the Google-only login screen
- Callback detection uses useLocation().hash (render-time), not window.location.hash
- Logout clears session: POST /api/auth/logout then /auth/me -> 401

## Cleanup
mongosh --eval "
use('test_database');
db.users.deleteMany({email: /test\.user\./});
db.user_sessions.deleteMany({session_token: /test_session/});
"
