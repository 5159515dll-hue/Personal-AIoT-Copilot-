import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "个人空间智能物联助手",
  description: "面向个人空间感知、推理、安全策略和审计的智能物联原型。"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
