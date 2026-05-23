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
  const sorted = [...sessions].sort((a: any, b: any) =>
    new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Inspection Queue</h1>
          <Link href="/" className="text-gray-400 hover:text-white text-sm">Home</Link>
        </div>

        {sorted.length === 0 ? (
          <div className="bg-gray-900 rounded-xl p-12 text-center text-gray-500">
            <p className="text-lg">No inspections yet</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sorted.map((s: any) => {
              const vehicle = [s.vehicle_year, s.vehicle_make, s.vehicle_model].filter(Boolean).join(' ');
              const date = s.started_at ? new Date(s.started_at).toLocaleString() : '';
              return (
                <Link key={s.id} href={"/sessions/" + s.id}
                  className="block bg-gray-900 hover:bg-gray-800 rounded-xl p-5 transition border border-gray-800">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-lg">{vehicle || 'Unknown Vehicle'}</p>
                      {s.vehicle_vin && <p className="text-xs text-gray-500 font-mono mt-0.5">VIN: {s.vehicle_vin}</p>}
                      {s.vehicle_mileage && <p className="text-sm text-gray-400 mt-0.5">{s.vehicle_mileage.toLocaleString()} miles</p>}
                      {s.customer_concern && <p className="text-sm text-gray-400 mt-1 italic">"{s.customer_concern}"</p>}
                      <p className="text-xs text-gray-600 mt-1">{date}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className={"px-3 py-1 rounded-full text-xs font-medium " + (
                        s.status === 'completed' ? 'bg-green-900 text-green-300' :
                        s.status === 'in_progress' ? 'bg-blue-900 text-blue-300' :
                        'bg-gray-700 text-gray-300'
                      )}>
                        {s.status.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
