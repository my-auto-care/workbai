import Link from 'next/link';

async function getReport(id: string) {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://167.99.153.77'}/sessions/${id}/report`, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

export default async function SessionPage({ params }: { params: { id: string } }) {
  const data = await getReport(params.id);
  const report = data?.report;

  if (!report) return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <p className="text-gray-400">Session not found</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Inspection Report</h1>
          <Link href="/queue" className="text-gray-400 hover:text-white text-sm">Queue</Link>
        </div>

        <div className="bg-gray-900 rounded-xl p-6 mb-6 border border-gray-800">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-gray-400">Session:</span> <span className="ml-2 font-mono">{report.session_id?.slice(0,8)}...</span></div>
            <div><span className="text-gray-400">Status:</span> <span className={"ml-2 font-medium " + (report.status === 'completed' ? 'text-green-400' : 'text-blue-400')}>{report.status}</span></div>
          </div>
          {report.customer_concern && (
            <div className="mt-4 pt-4 border-t border-gray-800">
              <span className="text-gray-400 text-sm">Customer concern:</span>
              <p className="mt-1">{report.customer_concern}</p>
            </div>
          )}
        </div>

        <h2 className="text-lg font-semibold mb-4">Findings ({report.findings?.length || 0})</h2>
        {(report.findings?.length === 0 || !report.findings) ? (
          <div className="bg-gray-900 rounded-xl p-8 text-center text-gray-500">No findings recorded</div>
        ) : (
          <div className="space-y-3">
            {report.findings.map((f: any) => (
              <div key={f.id} className="bg-gray-900 rounded-xl p-5 border border-gray-800">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium">{f.checklist_item_id || 'General finding'}</p>
                  <span className={"px-3 py-1 rounded-full text-xs font-medium " + (
                    f.condition === 'good' ? 'bg-green-900 text-green-300' :
                    f.condition === 'fair' ? 'bg-yellow-900 text-yellow-300' :
                    f.condition === 'poor' ? 'bg-red-900 text-red-300' :
                    'bg-gray-700 text-gray-300'
                  )}>{f.condition}</span>
                </div>
                {f.transcript && <p className="text-sm text-gray-300 mt-2">{f.transcript}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
