import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://167.99.153.77';

async function getStats() {
  try {
    const [sessions, checklists] = await Promise.all([
      fetch(`${API}/sessions`, { cache: 'no-store' }).then(r => r.json()),
      fetch(`${API}/checklists`, { cache: 'no-store' }).then(r => r.json()),
    ]);
    const completed = sessions.filter((s: any) => s.status === 'completed').length;
    const active = sessions.filter((s: any) => s.status === 'in_progress').length;
    return { total: sessions.length, completed, active, checklists: checklists.length };
  } catch { return { total: 0, completed: 0, active: 0, checklists: 0 }; }
}

async function getSessions() {
  try {
    const res = await fetch(`${API}/sessions`, { cache: 'no-store' });
    return res.ok ? res.json() : [];
  } catch { return []; }
}

export default async function AdminPage() {
  const [stats, sessions] = await Promise.all([getStats(), getSessions()]);

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Admin</h1>
          <Link href="/" className="text-gray-400 hover:text-white text-sm">Home</Link>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          {[
            { label: 'Total Sessions', value: stats.total, color: '' },
            { label: 'Active', value: stats.active, color: 'text-blue-400' },
            { label: 'Completed', value: stats.completed, color: 'text-green-400' },
            { label: 'Checklists', value: stats.checklists, color: '' },
          ].map(s => (
            <div key={s.label} className="bg-gray-900 rounded-xl p-5 border border-gray-800">
              <p className="text-gray-400 text-sm">{s.label}</p>
              <p className={"text-3xl font-bold mt-1 " + (s.color || 'text-white')}>{s.value}</p>
            </div>
          ))}
        </div>

        <div className="flex gap-3 mb-8">
          <Link href="/admin/checklists" className="bg-blue-600 hover:bg-blue-700 px-5 py-2.5 rounded-lg text-sm font-medium transition">
            Manage Checklists
          </Link>
          <Link href="/queue" className="bg-gray-700 hover:bg-gray-600 px-5 py-2.5 rounded-lg text-sm font-medium transition">
            Inspection Queue
          </Link>
        </div>

        <h2 className="text-lg font-semibold mb-4">Recent Sessions</h2>
        {sessions.length === 0 ? (
          <div className="bg-gray-900 rounded-xl p-8 text-center text-gray-500">No sessions yet</div>
        ) : (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400">
                  <th className="text-left p-4">Session ID</th>
                  <th className="text-left p-4">Status</th>
                  <th className="text-left p-4">Concern</th>
                  <th className="text-left p-4">Started</th>
                  <th className="p-4"></th>
                </tr>
              </thead>
              <tbody>
                {sessions.slice(0, 20).map((s: any) => (
                  <tr key={s.id} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/50">
                    <td className="p-4 font-mono text-gray-300">{s.id.slice(0, 8)}...</td>
                    <td className="p-4">
                      <span className={"px-2 py-0.5 rounded-full text-xs font-medium " + (
                        s.status === 'completed' ? 'bg-green-900 text-green-300' :
                        s.status === 'in_progress' ? 'bg-blue-900 text-blue-300' :
                        'bg-gray-700 text-gray-300'
                      )}>{s.status}</span>
                    </td>
                    <td className="p-4 text-gray-400 max-w-xs truncate">{s.customer_concern || '—'}</td>
                    <td className="p-4 text-gray-400">{s.started_at ? new Date(s.started_at).toLocaleString() : '—'}</td>
                    <td className="p-4">
                      <Link href={"/sessions/" + s.id} className="text-blue-400 hover:text-blue-300 text-xs">View</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
