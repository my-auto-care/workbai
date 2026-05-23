import Link from 'next/link';

async function getReport(id: string) {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://167.99.153.77'}/sessions/${id}/report`, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>{label}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h2 className="text-base font-semibold text-gray-200 mb-4">{title}</h2>
      {children}
    </div>
  );
}

export default async function SessionPage({ params }: { params: { id: string } }) {
  const data = await getReport(params.id);
  const report = data?.report;

  if (!report) return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <p className="text-gray-400">Session not found</p>
    </div>
  );

  const finding = report.findings?.find((f: any) => f.checklist_item_id === 'transcript_mode');
  const sd = finding?.structured_data || {};
  const vehicleDetail = sd.vehicle_detail || {};
  const recalls = sd.recalls || [];
  const repairs = sd.common_repairs || [];
  const maintenance = sd.maintenance || {};
  const warranty = sd.warranty || {};

  // Collect all photos across all findings
  const allPhotos: any[] = report.findings?.flatMap((f: any) => f.media || []).filter((m: any) => m.url) || [];

  const vehicle = [report.vehicle_year, report.vehicle_make, report.vehicle_model].filter(Boolean).join(' ');
  const startedAt = report.started_at ? new Date(report.started_at).toLocaleString() : '—';
  const completedAt = report.completed_at ? new Date(report.completed_at).toLocaleString() : '—';

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-4xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">{vehicle || 'Inspection Report'}</h1>
            <p className="text-gray-500 text-sm mt-1">Session {report.session_id?.slice(0, 8)}… · {startedAt}</p>
          </div>
          <div className="flex items-center gap-3">
            <Badge
              label={report.status?.replace('_', ' ')}
              color={report.status === 'completed' ? 'bg-green-900 text-green-300' : 'bg-blue-900 text-blue-300'}
            />
            <Link href="/queue" className="text-gray-400 hover:text-white text-sm">← Queue</Link>
          </div>
        </div>

        {/* Vehicle Info */}
        <Section title="🚗 Vehicle">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            {[
              ['Year',         report.vehicle_year],
              ['Make',         report.vehicle_make],
              ['Model',        report.vehicle_model],
              ['Mileage',      report.vehicle_mileage ? Number(report.vehicle_mileage).toLocaleString() + ' mi' : null],
              ['VIN',          report.vehicle_vin],
              ['Body',         vehicleDetail.body_type],
              ['Engine',       vehicleDetail.engine_description],
              ['Fuel',         vehicleDetail.fuel_type],
              ['Drive',        vehicleDetail.drive_type],
              ['Transmission', vehicleDetail.transmission],
              ['Horsepower',   vehicleDetail.horsepower ? vehicleDetail.horsepower + ' hp' : null],
              ['Torque',       vehicleDetail.torque ? vehicleDetail.torque + ' lb-ft' : null],
              ['MPG City',     vehicleDetail.mpg_city],
              ['MPG Hwy',      vehicleDetail.mpg_highway],
              ['MSRP',         vehicleDetail.msrp ? '$' + Number(vehicleDetail.msrp).toLocaleString() : null],
            ].filter(([, v]) => v).map(([label, value]) => (
              <div key={label as string}>
                <p className="text-gray-500 text-xs">{label}</p>
                <p className="text-white font-medium mt-0.5">{value}</p>
              </div>
            ))}
          </div>
          {report.customer_concern && (
            <div className="mt-4 pt-4 border-t border-gray-800">
              <p className="text-gray-500 text-xs">Customer Concern</p>
              <p className="text-white mt-1 italic">"{report.customer_concern}"</p>
            </div>
          )}
        </Section>

        {/* Inspection Notes */}
        {finding?.transcript && (
          <Section title="📋 Inspection Notes">
            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{finding.transcript}</p>
          </Section>
        )}

        {/* Photos */}
        {allPhotos.length > 0 && (
          <Section title={`📷 Photos (${allPhotos.length})`}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {allPhotos.map((photo: any) => (
                <a key={photo.id} href={photo.url} target="_blank" rel="noopener noreferrer"
                  className="block rounded-lg overflow-hidden border border-gray-700 hover:border-blue-500 transition">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={photo.url}
                    alt="Inspection photo"
                    className="w-full h-40 object-cover"
                  />
                </a>
              ))}
            </div>
          </Section>
        )}

        {/* Recalls */}
        <Section title={`⚠️ Recalls (${recalls.length})`}>
          {recalls.length === 0 ? (
            <p className="text-green-400 text-sm">No open recalls found</p>
          ) : (
            <div className="space-y-3">
              {recalls.map((r: any, i: number) => (
                <div key={i} className="border border-red-900 bg-red-950 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-medium text-red-300 text-sm">{r.component}</p>
                    <span className="text-xs text-gray-500">{r.date}</span>
                  </div>
                  <p className="text-sm text-gray-300">{r.summary}</p>
                  {r.remedy && <p className="text-xs text-gray-400 mt-1">Remedy: {r.remedy}</p>}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Maintenance */}
        {Object.keys(maintenance).length > 0 && (
          <Section title="🔧 Maintenance Schedule">
            <div className="space-y-2">
              {Object.entries(maintenance).slice(0, 10).map(([key, val]: [string, any]) => (
                <div key={key} className="flex justify-between text-sm border-b border-gray-800 pb-2">
                  <span className="text-gray-300 capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="text-gray-400">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Common Repairs */}
        {repairs.length > 0 && (
          <Section title="🛠️ Common Repairs for This Vehicle">
            <div className="space-y-2">
              {repairs.slice(0, 10).map((r: any, i: number) => (
                <div key={i} className="flex justify-between text-sm border-b border-gray-800 pb-2">
                  <span className="text-gray-300">{r.repair_name || r.name || JSON.stringify(r)}</span>
                  {r.cost && <span className="text-gray-400">${r.cost}</span>}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Warranty */}
        {Object.keys(warranty).length > 0 && (
          <Section title="🛡️ Warranty">
            <div className="grid grid-cols-2 gap-4 text-sm">
              {Object.entries(warranty).slice(0, 8).map(([key, val]: [string, any]) => (
                <div key={key}>
                  <p className="text-gray-500 text-xs capitalize">{key.replace(/_/g, ' ')}</p>
                  <p className="text-white mt-0.5">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</p>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Footer */}
        <div className="text-xs text-gray-600 text-center pb-8">
          Completed: {completedAt}
        </div>

      </div>
    </div>
  );
}
