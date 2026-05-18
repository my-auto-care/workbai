import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">Workbay AI</h1>
        <p className="text-gray-400 text-lg">AI-powered automotive inspection platform</p>
        <div className="flex gap-4 justify-center mt-8">
          <Link href="/queue" className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition">
            Inspection Queue
          </Link>
          <Link href="/admin" className="bg-gray-700 hover:bg-gray-600 px-6 py-3 rounded-lg font-medium transition">
            Admin
          </Link>
        </div>
      </div>
    </main>
  );
}
