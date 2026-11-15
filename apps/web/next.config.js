/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const isMock = process.env.NEXT_PUBLIC_MOCK === '1' || process.env.MOCK === '1';
    if (isMock) {
      return [];
    }
    const apiTarget = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiTarget}/:path*`,
      },
    ];
  },
  compress: false,
};

module.exports = nextConfig;
