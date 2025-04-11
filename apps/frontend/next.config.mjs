/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config) => {
    // Ignore the tw-animate-css module
    config.resolve.alias = {
      ...config.resolve.alias,
      'tw-animate-css': false,
    };
    return config;
  },
};

export default nextConfig; 