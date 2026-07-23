import React, { useState, useEffect } from 'react';
import { History, Copy, Check, ShieldCheck, Tag } from 'lucide-react';

export default function HistoryTab({ userId }) {
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    fetchClaims();
  }, [userId]);

  const fetchClaims = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/claims?userId=${userId || ''}`);
      const data = await res.json();
      if (data.success) {
        setClaims(data.claims || []);
      }
    } catch (err) {
      console.error('Error fetching claims:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (claimId, code) => {
    navigator.clipboard.writeText(code);
    setCopiedId(claimId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', gap: '14px', paddingBottom: '90px' }}>
      <div className="crafted-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
          <History color="var(--accent-amber)" size={18} />
          <h2 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Lịch Sử Nhận Code</h2>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
          Danh sách các Gifcode bạn đã mở khóa sau khi xem quảng cáo.
        </p>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-tertiary)', fontSize: '13px' }}>Đang tải lịch sử...</div>
      ) : claims.length === 0 ? (
        <div className="crafted-card" style={{ textAlign: 'center', padding: '36px 20px' }}>
          <Tag size={36} color="var(--text-tertiary)" style={{ marginBottom: '10px', opacity: 0.6 }} />
          <p style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>Chưa có Gifcode nào</p>
          <p style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
            Hãy chọn mục bất kỳ và xem video quảng cáo để nhận mã thưởng đầu tiên!
          </p>
        </div>
      ) : (
        claims.map(item => (
          <div key={item.id} className="crafted-card" style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <ShieldCheck size={14} color="var(--accent-cyan)" />
                <span style={{ fontWeight: '700', color: 'var(--accent-amber-light)', fontSize: '13px' }}>{item.categoryName}</span>
                <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>• {new Date(item.claimedAt).toLocaleString('vi-VN')}</span>
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)' }}>
                {item.code}
              </div>
            </div>

            <button 
              className="btn-secondary-crafted" 
              onClick={() => handleCopy(item.id, item.code)}
              style={{ padding: '6px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              {copiedId === item.id ? <Check size={13} color="var(--accent-amber)" /> : <Copy size={13} />}
              {copiedId === item.id ? 'Đã copy' : 'Copy'}
            </button>
          </div>
        ))
      )}
    </div>
  );
}
