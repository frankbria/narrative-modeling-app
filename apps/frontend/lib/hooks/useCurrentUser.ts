import { useSession } from 'next-auth/react';

export function useCurrentUser() {
  const { data: session, status } = useSession();
  
  return {
    user: session?.user,
    isLoaded: status !== 'loading',
    isSignedIn: !!session,
  };
}