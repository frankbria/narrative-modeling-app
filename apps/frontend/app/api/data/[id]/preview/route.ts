import { NextRequest, NextResponse } from 'next/server';
import { getToken } from 'next-auth/jwt';
import { auth } from '@/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Validate ID parameter
    if (!params.id || params.id === 'undefined') {
      return NextResponse.json(
        { error: 'Invalid dataset ID' },
        { status: 400 }
      );
    }
    
    // Get auth session
    const session = await auth();
    
    if (!session) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }
    
    // Get token from session or use the JWT token with secret
    let accessToken = session.accessToken;
    if (!accessToken) {
      const token = await getToken({ 
        req: request,
        secret: process.env.NEXTAUTH_SECRET 
      });
      accessToken = token?.accessToken || token?.access_token;
    }

    // Get query parameters
    const searchParams = request.nextUrl.searchParams;
    const rows = searchParams.get('rows') || '100';
    const offset = searchParams.get('offset') || '0';

    // Make request to backend
    const response = await fetch(
      `${API_URL}/data/${params.id}/preview?rows=${rows}&offset=${offset}`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken || 'default'}`,
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to fetch preview data' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Error fetching preview data:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}