import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/app/auth';

export async function POST(request: NextRequest) {
  try {
    // Get the current user session
    const session = await auth();
    
    if (!session?.user?.id) {
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
        'Authorization': `Bearer nextauth-${session.user.id}`,
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