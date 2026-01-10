import { useAuthenticator } from '@aws-amplify/ui-react';
import { useEffect, useState } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';

export const useAuth = () => {
  const { user, signOut } = useAuthenticator((context) => [context.user]);
  const [isLoading, setIsLoading] = useState(true);
  const [authToken, setAuthToken] = useState<string | null>(null);

  useEffect(() => {
    const getAuthToken = async () => {
      try {
        if (user) {
          const session = await fetchAuthSession();
          const token = session.tokens?.idToken?.toString();
          setAuthToken(token || null);
        }
      } catch (error) {
        console.error('Error getting auth token:', error);
        setAuthToken(null);
      } finally {
        setIsLoading(false);
      }
    };

    getAuthToken();
  }, [user]);

  return {
    user,
    signOut,
    isLoading,
    authToken,
    isAuthenticated: !!user,
  };
};