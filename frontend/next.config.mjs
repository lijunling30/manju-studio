/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 后端 mock 资产经 /storage 静态挂载，跨域代理避免 CORS 干扰
  async rewrites() {
    const backend = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
    return [
      { source: '/api/:path*', destination: `${backend}/api/:path*` },
      { source: '/storage/:path*', destination: `${backend}/storage/:path*` },
    ];
  },
};

export default nextConfig;
