import { useState, useEffect } from 'react';
import { useSession } from '@clerk/nextjs';

interface AISummary {
  overview: string;
  issues: string[];
  relationships: string[];
  suggestions: string[];
  rawMarkdown: string;
}

interface SummaryCache {
  [key: string]: {
    data: AISummary;
    timestamp: number;
  };
}

// Cache duration in milliseconds (5 minutes)
const CACHE_DURATION = 5 * 60 * 1000;

// In-memory cache for AI summaries
const summaryCache: SummaryCache = {};

/**
 * Hook to fetch and use the AI summary context for a dataset
 * @param datasetId The ID of the dataset or user ID
 * @returns Object containing the context string, raw markdown, and loading/error states
 */
export function useDatasetChatContext(datasetId: string | null) {
  const { session } = useSession();
  const [contextString, setContextString] = useState<string | null>(null);
  const [rawMarkdown, setRawMarkdown] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isAvailable, setIsAvailable] = useState<boolean>(false);

  useEffect(() => {
    const fetchAISummary = async () => {
      if (!datasetId) {
        setContextString(null);
        setRawMarkdown(null);
        setIsAvailable(false);
        return;
      }

      // Check if we have a cached version that's still valid
      const now = Date.now();
      const cachedData = summaryCache[datasetId];
      
      if (cachedData && (now - cachedData.timestamp < CACHE_DURATION)) {
        console.log('Using cached AI summary');
        setContextString(cachedData.data.rawMarkdown);
        setRawMarkdown(cachedData.data.rawMarkdown);
        setIsAvailable(true);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // First, check if this is a user ID and get the latest dataset for this user
        let actualDatasetId = datasetId;
        
        // If the ID looks like a Clerk user ID (starts with 'user_'), we need to fetch the latest dataset
        if (datasetId.startsWith('user_')) {
          // Ensure the URL has a protocol
          let backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
          if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
            backendUrl = `http://${backendUrl}`;
          }
          
          // Remove trailing /api if present
          backendUrl = backendUrl.replace(/\/api$/, '');
          
          // Fetch the latest dataset for this user
          const userDataResponse = await fetch(`${backendUrl}/api/user_data/latest`, {
            headers: {
              'Authorization': `Bearer ${await session?.getToken()}`
            }
          });
          
          if (userDataResponse.ok) {
            const userData = await userDataResponse.json();
            if (userData && userData._id) {
              actualDatasetId = userData._id;
            } else {
              // No dataset found for this user
              setIsAvailable(false);
              setContextString(null);
              setRawMarkdown(null);
              setIsLoading(false);
              return;
            }
          } else {
            // Error fetching user data
            const errorText = await userDataResponse.text();
            throw new Error(`Failed to fetch user data: ${errorText}`);
          }
        }
        
        // Now fetch the AI summary with the actual dataset ID
        let backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
          backendUrl = `http://${backendUrl}`;
        }
        
        // Remove trailing /api if present
        backendUrl = backendUrl.replace(/\/api$/, '');
        
        const response = await fetch(`${backendUrl}/api/user_data/${actualDatasetId}/ai-summary`, {
          headers: {
            'Authorization': `Bearer ${await session?.getToken()}`
          }
        });

        if (response.status === 404) {
          // AI summary not found - this is not an error, just not available yet
          console.log('AI summary not available yet');
          setIsAvailable(false);
          setContextString(null);
          setRawMarkdown(null);
        } else if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Failed to fetch AI summary: ${errorText}`);
        } else {
          const data: AISummary = await response.json();
          
          // Cache the result
          summaryCache[datasetId] = {
            data,
            timestamp: Date.now()
          };
          
          setContextString(data.rawMarkdown);
          setRawMarkdown(data.rawMarkdown);
          setIsAvailable(true);
        }
      } catch (err) {
        console.error('Error fetching AI summary:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch AI summary');
        setIsAvailable(false);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAISummary();
  }, [datasetId, session]);

  return {
    contextString,
    rawMarkdown,
    isLoading,
    error,
    isAvailable
  };
}

/**
 * Helper function to get the system prompt for OpenAI chat
 * @param datasetId The ID of the dataset or user ID
 * @returns A promise that resolves to the system prompt
 */
export async function getDatasetSystemPrompt(datasetId: string, session: { getToken: () => Promise<string | null> }): Promise<string> {
  try {
    // Check cache first
    const now = Date.now();
    const cachedData = summaryCache[datasetId];
    
    if (cachedData && (now - cachedData.timestamp < CACHE_DURATION)) {
      console.log('Using cached AI summary for system prompt');
      return cachedData.data.rawMarkdown;
    }
    
    // If the ID looks like a Clerk user ID (starts with 'user_'), we need to fetch the latest dataset
    let actualDatasetId = datasetId;
    if (datasetId.startsWith('user_')) {
      // Ensure the URL has a protocol
      let backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
        backendUrl = `http://${backendUrl}`;
      }
      
      // Remove trailing /api if present
      backendUrl = backendUrl.replace(/\/api$/, '');
      
      // Fetch the latest dataset for this user
      const userDataResponse = await fetch(`${backendUrl}/api/user_data/latest`, {
        headers: {
          'Authorization': `Bearer ${await session?.getToken()}`
        }
      });
      
      if (userDataResponse.ok) {
        const userData = await userDataResponse.json();
        if (userData && userData._id) {
          actualDatasetId = userData._id;
        } else {
          // No dataset found for this user
          return "I don't have any specific information about this dataset yet. Please upload a dataset and wait for the AI analysis to complete.";
        }
      } else {
        // Error fetching user data
        const errorText = await userDataResponse.text();
        throw new Error(`Failed to fetch user data: ${errorText}`);
      }
    }
    
    // Now fetch the AI summary with the actual dataset ID
    let backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
      backendUrl = `http://${backendUrl}`;
    }
    
    // Remove trailing /api if present
    backendUrl = backendUrl.replace(/\/api$/, '');
    
    const response = await fetch(`${backendUrl}/api/user_data/${actualDatasetId}/ai-summary`, {
      headers: {
        'Authorization': `Bearer ${await session?.getToken()}`
      }
    });

    if (response.status === 404) {
      // Return a default context string if AI summary is not available
      return "I don't have any specific information about this dataset yet. Please upload a dataset and wait for the AI analysis to complete.";
    } else if (!response.ok) {
      throw new Error(`Failed to fetch AI summary: ${await response.text()}`);
    }

    const data: AISummary = await response.json();
    
    // Cache the result
    summaryCache[datasetId] = {
      data,
      timestamp: now
    };
    
    return data.rawMarkdown;
  } catch (err) {
    console.error('Error fetching AI summary:', err);
    throw err;
  }
} 