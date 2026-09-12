import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    // Await params in Next.js 15
    const { id } = await params;

    // Validate ID parameter
    if (!id || id === 'undefined') {
      return NextResponse.json(
        { error: 'Invalid dataset ID' },
        { status: 400 }
      );
    }
    
    // The backend accepts exactly one credential: the HS256 API JWT minted in the
    // NextAuth session callback (sub=userId). Never the OAuth provider's access
    // token — that is Google's/GitHub's credential, not ours — and never a
    // placeholder: without a token this is a 401, not a guess (#527).
    const session = await auth();
    const apiToken = session?.apiToken;
    if (!session || !apiToken) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    // Get query parameters
    const searchParams = request.nextUrl.searchParams;
    const rows = searchParams.get('rows') || '100';
    const offset = searchParams.get('offset') || '0';

    // Make request to backend
    const response = await fetch(
      `${API_URL}/data/${id}/preview?rows=${rows}&offset=${offset}`,
      {
        headers: {
          'Authorization': `Bearer ${apiToken}`,
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