'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://167.99.153.77';

interface Item {
  id: string;
  label: string;
  category: string;
}

export default function NewChecklistPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [items, setItems] = useState<Item[]>([{ id: 'item_1', label: '', category: '' }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const addItem = () => setItems(prev => [...prev, { id: `item_${Date.now()}`, label: '', category: '' }]);
  const removeItem = (idx: number) => setItems(prev => prev.filter((_, i) => i !== idx));
  const updateItem = (idx: number, field: keyof Item, value: string) =>
    setItems(prev => prev.map((item, i) => i === idx ? { ...item, [field]: value } : item));

  const save = async () => {
    if (!name.trim()) { setError('Name is required'); return; }
    if (items.some(i => !i.label.trim())) { setError('All items need a label'); return; }
    setSaving(true); setError('');
    try {
      const res = await fetch(`${API}/checklists`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, items: { items } }),
      });
      if (!res.ok) throw new Error('Failed to save');
      router.push('/admin/checklists');
    } catch (e: any) {
      setError(e.message);
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">New Checklist</h1>
          <Link href="/admin/checklists" className="text-gray-400 hover:text-white text-sm">Cancel</Link>
        </div>

        {error && <div className="bg-red-900/50 border border-red-700 text-red-300 rounded-lg p-3 mb-6 text-sm">{error}</div>}

        <div className="space-y-6">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Checklist Name</label>
            <input
              value={name} onChange={e => setName(e.target.value)}
              placeholder="e.g. Standard 50-Point Inspection"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm text-gray-400">Checklist Items</label>
              <button onClick={addItem} className="text-blue-400 hover:text-blue-300 text-sm">+ Add Item</button>
            </div>
            <div className="space-y-2">
              {items.map((item, idx) => (
                <div key={item.id} className="flex gap-2">
                  <input
                    value={item.category} onChange={e => updateItem(idx, 'category', e.target.value)}
                    placeholder="Category"
                    className="w-32 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  />
                  <input
                    value={item.label} onChange={e => updateItem(idx, 'label', e.target.value)}
                    placeholder="Item label"
                    className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  />
                  <button onClick={() => removeItem(idx)} className="text-gray-500 hover:text-red-400 px-2 text-lg">×</button>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={save} disabled={saving}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-6 py-3 rounded-lg font-medium transition"
          >
            {saving ? 'Saving...' : 'Create Checklist'}
          </button>
        </div>
      </div>
    </div>
  );
}
