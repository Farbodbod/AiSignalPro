import './globals.css'
export const metadata = {
  title: 'Ai Signal Pro',
  description: 'Advanced Trading Dashboard',
}
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-black text-gray-200 font-sans">{children}</body>
    </html>
  )
}
