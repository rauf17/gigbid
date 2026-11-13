// synthetic: true
import React, { useEffect, useState } from 'react';

export const LiveMetrics: React.FC = () => {
  const [cpu, setCpu] = useState(45);
  useEffect(() => {
    const timer = setInterval(() => setCpu(Math.floor(40 + Math.random() * 30)), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="p-4 bg-slate-900 text-white rounded-lg">
      <h4 className="text-sm text-slate-400">Cluster CPU Load</h4>
      <div className="text-2xl font-mono">{cpu}%</div>
    </div>
  );
};
