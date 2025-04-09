import { NextRequest, NextResponse } from 'next/server';
import { getAuth } from '@clerk/nextjs/server';

export async function POST(request: NextRequest) {
  try {
    // Get the current user
    const { userId } = getAuth(request);
    
    if (!userId) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }
    
    // Get the data from the request
    const data = await request.json();
    
    // Forward the request to the backend
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const response = await fetch(`${backendUrl}/api/store`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userId}`,
      },
      body: JSON.stringify(data),
    });
    
    // Check if the response is ok
    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: `Backend error: ${errorText}` },
        { status: response.status }
      );
    }
    
    // Return the response from the backend
    const result = await response.json();
    return NextResponse.json(result);
    
  } catch (error) {
    console.error('Error storing data:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
} 