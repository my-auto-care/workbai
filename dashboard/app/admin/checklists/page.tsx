import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://167.99.153.77';

async function getChecklists() {
  try {
    const res = await fetch(`${API}/checklists`, { cache: 'no-store' });
    return res.ok ? res.json() : [];
  } catch { return []; }
}

export default async function ChecklistsPage() {
  const checklists = await getChecklists();

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Checklists</h1>
          <div className="flex gap-3">
            <Link href="/admin/checklists/new" className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-sm font-medium transition">
              + New Checklist
            </Link>
            <Link href="/admin" className="text-gray-400 hover:text-white text-sm self-center">Admin</Link>
          </div>
        </div>

        {checklists.length === 0 ? (
          <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-500">
            <p className="text-lg">No checklists yet</p>
            <Link href="/admin/checklists/new" className="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
              Create your first checklist
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {checklists.map((c: any) => (
              <div key={c.id} className="bg-gray-900 rounded-xl p-5 border border-gray-800 flex items-center justify-between">
                <div>
                  <p className="font-medium">{c.name}</p>
                  <p className="text-sm text-gray-400 mt-1">v{c.version} · {c.vehicle_filter && Object.keys(c.vehicle_filter).length > 0 ? JSON.stringify(c.vehicle_filter) : 'All vehicles'}</p>
                </div>
                <Link href={"/admin/checklists/" + c.id} className="text-blue-400 hover:text-blue-300 text-sm">Edit →</Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
