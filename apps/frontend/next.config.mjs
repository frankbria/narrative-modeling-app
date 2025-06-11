/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker production builds
  output: process.env.NODE_ENV === 'production' ? 'standalone' : undefined,
  
  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
    ];
  },
  
  webpack: (config) => {
    // Ignore the tw-animate-css module
    config.resolve.alias = {
      ...config.resolve.alias,
      'tw-animate-css': false,
    };
    return config;
  },
  
  // Experimental features for better performance
  experimental: {
    serverComponentsExternalPackages: ['@prisma/client'],
  },
};

export default nextConfig; 