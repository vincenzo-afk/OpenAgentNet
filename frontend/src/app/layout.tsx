import "./globals.css";

export const metadata = {
  title: "OpenAgentNet Dashboard",
  description: "Agent registry and network dashboard for the OpenAgentNet protocol",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
