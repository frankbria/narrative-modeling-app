import { getSession } from 'next-auth/react';

const skipAuth = process.env.NEXT_PUBLIC_SKIP_AUTH === 'true';

export async function getAuthToken() {
  // In skip auth mode, return a token that maps to dev-user-default
  if (skipAuth) {
    return 'default';  // This will map to 'dev-user-default' in the backend
  }
  
  const session = await getSession();
  
  // For now, we'll use a placeholder token
  // In a real implementation, you'd want to:
  // 1. Use the NextAuth JWT directly, or
  // 2. Create a custom endpoint to exchange the session for an API token
  
  if (session?.user?.id) {
    // Create a simple token that the backend can validate
    // This is temporary - in production you'd want proper JWT signing
    return `nextauth-${session.user.id}`;
  }
  
  return null;
}