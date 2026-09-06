import os from "node:os";

import type { NextConfig } from "next";

/**
 * Non-internal IPv4 addresses of this machine, e.g. "192.168.86.248".
 */
function lanAddresses(): string[] {
  return Object.values(os.networkInterfaces())
    .flat()
    .filter((iface): iface is os.NetworkInterfaceInfo => iface !== undefined)
    .filter((iface) => iface.family === "IPv4" && !iface.internal)
    .map((iface) => iface.address);
}

const nextConfig: NextConfig = {
  /**
   * Next.js blocks cross-origin requests to dev-only resources (`/_next/hmr`) by
   * default, so opening the LAN URL the launcher advertises silently kills Fast Refresh.
   *
   * The address is detected at startup rather than written literally: it is
   * DHCP-assigned, so a hardcoded value would break on lease renewal and would be
   * meaningless on any other machine cloning this repo. `allowedDevOrigins` only
   * accepts exact origins — its wildcard support is limited to subdomains, so
   * "192.168.x.*" is not an option.
   *
   * This affects development only; it has no effect on a production build.
   */
  allowedDevOrigins: lanAddresses(),
};

export default nextConfig;
