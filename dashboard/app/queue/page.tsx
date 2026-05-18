import Link from 'next/link';

async function getSessions() {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://167.99.153.77'}/sessions`, { cache: 'no-store' });
    if (!res.ok) return [];
    return res.json();
  } catch { return []; }
}

export default async function QueuePage() {
  const sessions = await getSessions();

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Inspection Queue</h1>
          <Link href="/" className="text-gray-400 hover:text-white text-sm">Home</Link>
        </div>

        {sessions.length === 0 ? (
          <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-500">
            <p className="text-lg">No active inspections</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((s: any) => (
              <Link key={s.id} href={"/sessions/" + s.id}
                className="block bg-gray-900 hover:bg-gray-800 rounded-xl p-5 transition border border-gray-800">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Session {s.id.slice(0, 8)}...</p>
                    <p className="text-sm text-gray-400 mt-1">{s.customer_concern || 'No concern noted'}</p>
                  </div>
                  <span className={"px-3 py-1 rounded-full text-xs font-medium " + (
                    s.status === 'completed' ? 'bg-green-900 text-green-300' :
                    s.status === 'in_progress' ? 'bg-blue-900 text-blue-300' :
                    'bg-gray-700 text-gray-300'
                  )}>
                    {s.status}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
