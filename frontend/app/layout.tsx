import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Running Route Optimizer",
  description: "Generate distance- and elevation-optimized running routes from OpenStreetMap data.",
};

// Runs before hydration so the correct theme is set on <html> before the
// first paint -- otherwise the page would flash the light theme (the CSS
// default) even for a user whose stored/system preference is dark.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("theme");
    var theme =
      stored === "dark" || stored === "light"
        ? stored
        : window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
