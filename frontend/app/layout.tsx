import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '漫镜工场 · ManJu Studio',
  description: 'AI 漫剧工业化生产平台：小说 → 剧本 → 分镜 → 角色 → 视频 → 成片',
};

/** 首帧前应用主题，避免闪烁 */
const themeScript = `
(function () {
  try {
    var t = localStorage.getItem('manju_theme') || 'dark';
    var resolved = t === 'system'
      ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
      : t;
    document.documentElement.dataset.theme = resolved;
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="h-screen overflow-hidden">{children}</body>
    </html>
  );
}
