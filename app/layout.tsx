import type { Metadata } from "next";
import "bootstrap/dist/css/bootstrap.min.css";
import "@xyflow/react/dist/style.css";
import "./styles.css";

export const metadata: Metadata = {
  title: "ArchFlow AI",
  description: "AI-powered system design visualization platform"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
