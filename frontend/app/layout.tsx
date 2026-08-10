import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Running Route Optimizer",
  description: "Generate distance- and elevation-optimized running routes from OpenStreetMap data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
