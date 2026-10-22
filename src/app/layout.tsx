import type { Metadata } from 'next';
import { Archivo, Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/components/auth-provider';

const display = Archivo({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-display' });
const sans = Geist({ subsets: ['latin'], weight: ['400', '500', '600'], variable: '--font-sans' });
const mono = Geist_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'ReconAI · Document reconciliation',
  description: 'Match purchase orders, receipts and invoices, with every finding tied to the line it came from.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
