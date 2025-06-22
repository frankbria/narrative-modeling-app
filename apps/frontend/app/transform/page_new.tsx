'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSearchParams } from 'next/navigation';

export default function TransformPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const datasetId = searchParams.get('datasetId');

  useEffect(() => {
    // Redirect to the prepare page which has the integrated transformation pipeline
    if (datasetId) {
      router.replace(`/prepare?datasetId=${datasetId}`);
    } else {
      router.replace('/prepare');
    }
  }, [router, datasetId]);

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <h2 className="text-xl font-semibold mb-2">Redirecting...</h2>
        <p className="text-gray-600">You'll be redirected to the integrated transformation pipeline.</p>
      </div>
    </div>
  );
}
