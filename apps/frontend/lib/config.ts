import { publicEnv } from '@/lib/runtimeEnv'

export const API_BASE_URL = publicEnv('NEXT_PUBLIC_API_URL') || 'http://localhost:8000/api/v1';
