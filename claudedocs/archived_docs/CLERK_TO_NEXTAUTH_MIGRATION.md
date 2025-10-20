# Clerk to NextAuth Migration Plan

## Overview
Migrating from Clerk to NextAuth with Google and GitHub providers.

## Migration Steps

### 1. Frontend Dependencies
- [x] Install NextAuth and required packages
- [ ] Remove Clerk packages
- [x] Install MongoDB adapter for NextAuth

### 2. Frontend Components to Update
- [x] `app/layout.tsx` - Replace ClerkProvider with SessionProvider
- [x] `components/Sidebar.tsx` - Replace UserButton with custom user menu
- [ ] All pages using `useAuth()` or `useUser()` hooks (1 done as example)
- [ ] Update API calls to use NextAuth session tokens

### 3. Backend Authentication
- [x] Create new JWT validation for NextAuth tokens (nextauth_auth.py)
- [ ] Update all API endpoints to use new auth middleware
- [ ] Remove Clerk-specific auth code

### 4. Environment Variables
- [x] Document required Google OAuth credentials
- [x] Document required GitHub OAuth credentials
- [x] Document NextAuth secret
- [ ] Remove Clerk variables from actual .env files

### 5. Database Changes
- [ ] NextAuth will create its own collections in MongoDB
- [ ] May need to migrate existing user data

## Files to Update

### Frontend
1. `/app/layout.tsx` - Remove ClerkProvider
2. `/components/Sidebar.tsx` - Replace UserButton
3. `/app/explore/[id]/page.tsx` - Update auth hooks
4. `/app/model/page.tsx` - Update auth hooks
5. `/app/predict/page.tsx` - Update auth hooks
6. `/app/load/page.tsx` - Update auth hooks
7. `/app/review/page.tsx` - Update auth hooks
8. `/app/explore/page.tsx` - Update auth hooks
9. `/app/monitor/page.tsx` - Update auth hooks
10. `/app/settings/api/page.tsx` - Update auth hooks
11. `/lib/hooks/useChunkedUpload.ts` - Update auth token
12. `/lib/hooks/useDatasetChatContext.ts` - Update auth
13. `/components/ModelTrainingButton.tsx` - Update auth
14. `/components/AIChat.tsx` - Update auth
15. `/middleware.tsx` - Replace Clerk middleware

### Backend
1. `/app/auth/clerk_auth.py` - Replace with NextAuth JWT validation
2. All API routes using `get_current_user_id`

## Completed Items

### Frontend
1. ✅ Installed next-auth@beta, @auth/mongodb-adapter, mongodb
2. ✅ Created auth.ts with Google and GitHub providers
3. ✅ Created custom sign-in page at /auth/signin
4. ✅ Created SessionProvider wrapper component
5. ✅ Updated layout.tsx to use NextAuth
6. ✅ Updated Sidebar with custom user dropdown (replaced UserButton)
7. ✅ Created middleware.ts for NextAuth
8. ✅ Created useCurrentUser hook as Clerk replacement
9. ✅ Created getAuthToken helper
10. ✅ Updated explore/[id]/page.tsx as migration example

### Backend
1. ✅ Created nextauth_auth.py for JWT validation
2. ✅ Updated .env.example with new variables

## Remaining Tasks

### High Priority
1. Configure Google OAuth app at https://console.cloud.google.com
2. Configure GitHub OAuth app at https://github.com/settings/developers
3. Generate NEXTAUTH_SECRET with: `openssl rand -base64 32`
4. Update remaining pages to use NextAuth hooks
5. Update backend API routes to use nextauth_auth.py
6. Test authentication flow end-to-end

### Medium Priority
1. Remove Clerk packages from package.json
2. Delete Clerk-specific files
3. Update all API calls to handle NextAuth tokens
4. Create user migration script if needed

### Low Priority
1. Add Magic Link provider after email service selection
2. Customize sign-in/error pages further
3. Add user profile management pages