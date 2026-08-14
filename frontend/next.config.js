/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  env: {
    // Backend base URL (defaults to the local dev stack).
    API_BASE_URL: process.env.API_BASE_URL || "http://localhost:8000/v1",
  },
};

module.exports = nextConfig;
