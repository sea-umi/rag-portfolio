import '../globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = { title: '社内文書検索AI', description: 'RAG検索チャット' };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="ja"><body>{children}</body></html>; }
