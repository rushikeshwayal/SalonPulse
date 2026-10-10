import type { Metadata, Viewport } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "SalonPulse | Salon operations", description: "Customer visits and salon performance.", applicationName: "SalonPulse", appleWebApp: { capable: true, statusBarStyle: "default", title: "SalonPulse" } };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f7f7fb" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
