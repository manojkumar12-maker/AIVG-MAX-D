/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["*.vercel.run"],
  transpilePackages: ['studio', 'ai-agent', 'workflow-builder', 'design-agent'],
};

export default nextConfig;
