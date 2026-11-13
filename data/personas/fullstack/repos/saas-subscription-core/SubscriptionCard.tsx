// synthetic: true
import React from 'react';

interface Props {
  planName: string;
  priceMonthly: number;
  features: string[];
  onSelect: () => void;
}

export const SubscriptionCard: React.FC<Props> = ({ planName, priceMonthly, features, onSelect }) => {
  return (
    <div className="border rounded-xl p-6 shadow-sm hover:shadow-md transition">
      <h3 className="text-xl font-bold">{planName}</h3>
      <p className="text-3xl font-extrabold my-4">${priceMonthly}<span className="text-sm font-normal">/mo</span></p>
      <ul className="space-y-2 mb-6">
        {features.map((f, i) => <li key={i} className="text-sm text-gray-600">✓ {f}</li>)}
      </ul>
      <button onClick={onSelect} className="w-full bg-blue-600 text-white py-2 rounded-lg font-medium">Select Plan</button>
    </div>
  );
};
