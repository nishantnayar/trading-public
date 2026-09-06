import type { NextConfig } from "next";

/**
 * No `allowedDevOrigins` entry is needed: the launcher binds `next dev` to 127.0.0.1
 * (see `scripts/start.py`), so the dev server is never reachable over the LAN and
 * cannot receive the cross-origin requests that Next blocks by default. Remote access
 * is a deployment concern, not a dev-server one.
 */
const nextConfig: NextConfig = {};

export default nextConfig;
