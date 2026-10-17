import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Nav } from "@/components/Nav";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "WIMBL",
  description: "A self-improving family of football-travel agents running on NVIDIA Nemotron, served by Crusoe Managed Inference.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-white font-sans text-forest antialiased`}>
        <Nav />
        <main id="main" className="mx-auto max-w-6xl px-4 pb-32 pt-12 sm:px-8 sm:pt-16">{children}</main>
      </body>
    </html>
  );
}
