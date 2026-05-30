/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 단일 프로세스(.exe) 배포: Next.js를 정적 사이트로 export하여
  // FastAPI가 동일 오리진에서 직접 서빙한다. (next start 미사용)
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true
  }
};

export default nextConfig;
