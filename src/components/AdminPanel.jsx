import React, { useState, useEffect } from 'react';
import { Settings, Plus, Edit2, Trash2, Key, CheckCircle, Database, Layers, ArrowLeft, RefreshCw, FileText } from 'lucide-react';

export default function AdminPanel({ onBack }) {
  const [password, setPassword] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loginError, setLoginError] = useState('');

  // Data states
  const [categories, setCategories] = useState([]);
  const [codes, setCodes] = useState([]);
  const [counts, setCounts] = useState({});
  const [selectedCatId, setSelectedCatId] = useState('');
  const [codesText, setCodesText] = useState('');
  
  // Category Form State
  const [editingCategory, setEditingCategory] = useState(null);
  const [catName, setCatName] = useState('');
  const [catDesc, setCatDesc] = useState('');
  const [catIcon, setCatIcon] = useState('🔥');

  // Rules Text State
  const [rulesText, setRulesText] = useState('');
  
  const [message, setMessage] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      setLoginError('');
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });
      const data = await res.json();
      if (data.success) {
        setIsLoggedIn(true);
        fetchAdminData(password);
      } else {
        setLoginError(data.message || 'Mật khẩu không đúng!');
      }
    } catch (err) {
      setLoginError('Lỗi kết nối Server!');
    }
  };

  const fetchAdminData = async (pwd) => {
    try {
      const p = pwd || password;
      const resCat = await fetch('/api/categories');
      const dataCat = await resCat.json();
      if (dataCat.success) {
        setCategories(dataCat.categories || []);
        if (dataCat.categories.length > 0 && !selectedCatId) {
          setSelectedCatId(dataCat.categories[0].id);
        }
      }

      const resSettings = await fetch('/api/settings');
      const dataSettings = await resSettings.json();
      if (dataSettings.success) {
        setRulesText(dataSettings.settings?.rulesText || '');
      }

      const resCodes = await fetch('/api/admin/codes', {
        headers: { 'x-admin-password': p }
      });
      const dataCodes = await resCodes.json();
      if (dataCodes.success) {
        setCodes(dataCodes.codes || []);
        setCounts(dataCodes.counts || {});
      }
    } catch (err) {
      console.error('Error fetching admin data:', err);
    }
  };

  const showMsg = (txt) => {
    setMessage(txt);
    setTimeout(() => setMessage(''), 3500);
  };

  const handleSaveCategory = async (e) => {
    e.preventDefault();
    if (!catName.trim()) return;

    try {
      const body = {
        id: editingCategory ? editingCategory.id : undefined,
        name: catName,
        description: catDesc,
        icon: catIcon,
        active: true
      };

      const res = await fetch('/api/admin/categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-admin-password': password
        },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (data.success) {
        showMsg(data.message);
        setCatName('');
        setCatDesc('');
        setCatIcon('🔥');
        setEditingCategory(null);
        fetchAdminData();
      } else {
        alert(data.message);
      }
    } catch (err) {
      alert('Lỗi lưu danh mục!');
    }
  };

  const handleEditCatClick = (cat) => {
    setEditingCategory(cat);
    setCatName(cat.name);
    setCatDesc(cat.description || '');
    setCatIcon(cat.icon || '🔥');
  };

  const handleDeleteCat = async (catId) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa danh mục này?')) return;
    try {
      const res = await fetch(`/api/admin/categories/${catId}`, {
        method: 'DELETE',
        headers: { 'x-admin-password': password }
      });
      const data = await res.json();
      if (data.success) {
        showMsg(data.message);
        fetchAdminData();
      }
    } catch (err) {
      alert('Lỗi xóa danh mục');
    }
  };

  const handleAddCodes = async (e) => {
    e.preventDefault();
    if (!selectedCatId || !codesText.trim()) return;

    try {
      const res = await fetch('/api/admin/codes/add', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-admin-password': password
        },
        body: JSON.stringify({
          categoryId: selectedCatId,
          codesText
        })
      });
      const data = await res.json();
      if (data.success) {
        showMsg(data.message);
        setCodesText('');
        fetchAdminData();
      } else {
        alert(data.message);
      }
    } catch (err) {
      alert('Lỗi nạp gifcode!');
    }
  };

  const handleDeleteCode = async (codeId) => {
    try {
      const res = await fetch(`/api/admin/codes/${codeId}`, {
        method: 'DELETE',
        headers: { 'x-admin-password': password }
      });
      const data = await res.json();
      if (data.success) {
        fetchAdminData();
      }
    } catch (err) {
      alert('Lỗi xóa code');
    }
  };

  const handleSaveRules = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/admin/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-admin-password': password
        },
        body: JSON.stringify({ rulesText })
      });
      const data = await res.json();
      if (data.success) {
        showMsg('Đã cập nhật Quy Định thành công!');
      } else {
        alert(data.message || 'Lỗi cập nhật quy định');
      }
    } catch (err) {
      alert('Lỗi kết nối Server!');
    }
  };

  if (!isLoggedIn) {
    return (
      <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button onClick={onBack} className="btn-secondary-crafted" style={{ padding: '6px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ArrowLeft size={14} /> Quay lại
          </button>
        </div>

        <div className="crafted-card" style={{ maxWidth: '380px', margin: '20px auto', padding: '24px' }}>
          <div style={{ textAlign: 'center', marginBottom: '20px' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'var(--accent-amber-bg)', border: '1px solid var(--border-amber)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
              <Key size={22} color="var(--accent-amber)" />
            </div>
            <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)' }}>ĐĂNG NHẬP ADMIN</h2>
            <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>Nhập mật khẩu quản trị hệ thống</p>
          </div>

          <form onSubmit={handleLogin}>
            <div className="form-field-group">
              <label>Mật khẩu Admin</label>
              <input 
                type="password"
                className="form-input-control"
                placeholder="Mặc định: admin123"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>

            {loginError && (
              <div style={{ color: '#ef4444', fontSize: '12px', marginBottom: '12px', textAlign: 'center' }}>
                {loginError}
              </div>
            )}

            <button type="submit" className="btn-primary-crafted">
              XÁC NHẬN ĐĂNG NHẬP
            </button>
          </form>
        </div>
      </div>
    );
  }

  const selectedCatObj = categories.find(c => c.id === selectedCatId);

  return (
    <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', paddingBottom: '90px' }}>
      {/* Header Bar */}
      <div className="admin-header-bar crafted-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Settings color="var(--accent-amber)" size={18} />
          <div>
            <h2 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)' }}>QUẢN TRỊ ADMIN</h2>
            <span style={{ fontSize: '11px', color: 'var(--accent-cyan)' }}>● Hệ thống sẵn sàng</span>
          </div>
        </div>
        <button onClick={onBack} className="btn-secondary-crafted">
          Về MiniApp
        </button>
      </div>

      {message && (
        <div style={{ background: 'rgba(6, 182, 212, 0.1)', border: '1px solid var(--accent-cyan)', color: 'var(--accent-cyan)', padding: '10px 14px', borderRadius: '8px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle size={15} />
          {message}
        </div>
      )}

      {/* SECTION 1: CÀI ĐẶT QUY ĐỊNH & THỂ LỆ */}
      <div className="crafted-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <FileText color="var(--accent-amber)" size={16} />
          <h3 style={{ fontSize: '14px', fontWeight: '600' }}>1. QUY ĐỊNH & THỂ LỆ</h3>
        </div>

        <form onSubmit={handleSaveRules}>
          <div className="form-field-group">
            <label>Nội dung thể lệ (Hiển thị công khai):</label>
            <textarea 
              className="form-input-control"
              placeholder="Nhập nội dung quy định..."
              value={rulesText}
              onChange={e => setRulesText(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn-primary-crafted" style={{ padding: '10px', fontSize: '13px' }}>
            LƯU THỂ LỆ QUY ĐỊNH
          </button>
        </form>
      </div>

      {/* SECTION 2: QUẢN LÝ DANH MỤC */}
      <div className="crafted-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers color="var(--accent-amber)" size={16} />
            <h3 style={{ fontSize: '14px', fontWeight: '600' }}>2. DANH MỤC NHÀ CÁI</h3>
          </div>
          {editingCategory && (
            <button onClick={() => { setEditingCategory(null); setCatName(''); setCatDesc(''); setCatIcon('🔥'); }} className="btn-secondary-crafted" style={{ padding: '4px 8px', fontSize: '11px' }}>
              + Thêm mục mới
            </button>
          )}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' }}>
          {categories.map(cat => (
            <div key={cat.id} style={{ background: selectedCatId === cat.id ? 'var(--accent-amber-bg)' : 'rgba(255,255,255,0.03)', border: selectedCatId === cat.id ? '1px solid var(--border-amber)' : '1px solid var(--border-subtle)', padding: '6px 12px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span>{cat.icon}</span>
              <span style={{ fontWeight: '600', color: selectedCatId === cat.id ? 'var(--accent-amber-light)' : 'var(--text-primary)' }}>{cat.name}</span>
              
              <button onClick={() => handleEditCatClick(cat)} style={{ background: 'none', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', marginLeft: '4px' }}>
                <Edit2 size={12} />
              </button>
              <button onClick={() => handleDeleteCat(cat.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        <form onSubmit={handleSaveCategory} style={{ background: 'var(--bg-app)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--accent-amber-light)', marginBottom: '10px' }}>
            {editingCategory ? `✏️ Đổi Tên / Sửa Danh Mục: ${editingCategory.name}` : '➕ Thêm Danh Mục Mới'}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '70px 1fr', gap: '8px', marginBottom: '8px' }}>
            <div>
              <label style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>Icon</label>
              <input type="text" className="form-input-control" value={catIcon} onChange={e => setCatIcon(e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>Tên Danh Mục</label>
              <input type="text" className="form-input-control" placeholder="Tên..." value={catName} onChange={e => setCatName(e.target.value)} required />
            </div>
          </div>

          <div className="form-field-group" style={{ marginBottom: '8px' }}>
            <label style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>Mô Tả</label>
            <input type="text" className="form-input-control" placeholder="Mô tả ngắn..." value={catDesc} onChange={e => setCatDesc(e.target.value)} />
          </div>

          <button type="submit" className="btn-primary-crafted" style={{ padding: '8px', fontSize: '13px' }}>
            {editingCategory ? 'LƯU THAY ĐỔI' : 'TẠO DANH MỤC'}
          </button>
        </form>
      </div>

      {/* SECTION 3: NẠP GIFCODE HÀNG LOẠT */}
      <div className="crafted-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Database color="var(--accent-cyan)" size={16} />
          <h3 style={{ fontSize: '14px', fontWeight: '600' }}>3. NẠP DỮ LIỆU GIFCODE</h3>
        </div>

        <form onSubmit={handleAddCodes}>
          <div className="form-field-group">
            <label>Chọn Mục Cần Nạp Code</label>
            <select className="form-input-control" value={selectedCatId} onChange={e => setSelectedCatId(e.target.value)} required>
              {categories.map(c => (
                <option key={c.id} value={c.id}>
                  {c.icon} {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-field-group">
            <label>Danh Sách Code (Mỗi mã 1 dòng)</label>
            <textarea 
              className="form-input-control"
              placeholder={`TANTHU-VIP888-100K\nTANTHU-LUCKY999-50K`}
              value={codesText}
              onChange={e => setCodesText(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn-primary-crafted" style={{ padding: '10px' }}>
            <Plus size={16} /> NẠP GIFCODE VÀO MỤC {selectedCatObj ? selectedCatObj.name : ''}
          </button>
        </form>
      </div>

      {/* SECTION 4: KHO CODE */}
      <div className="crafted-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '600' }}>4. GIFCODE TRONG KHO</h3>
          <button onClick={() => fetchAdminData()} className="btn-secondary-crafted" style={{ padding: '4px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <RefreshCw size={12} /> Làm mới
          </button>
        </div>

        <div style={{ maxHeight: '220px', overflowY: 'auto' }}>
          {codes.filter(c => !selectedCatId || c.categoryId === selectedCatId).length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: '16px', fontSize: '12px' }}>
              Chưa có code nào. Vui lòng nạp code phía trên!
            </div>
          ) : (
            codes.filter(c => !selectedCatId || c.categoryId === selectedCatId).map(item => (
              <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', marginBottom: '4px', border: '1px solid var(--border-subtle)' }}>
                <div>
                  <span style={{ fontFamily: 'monospace', fontWeight: '600', fontSize: '12px', color: item.isUsed ? 'var(--text-tertiary)' : 'var(--accent-amber-light)', textDecoration: item.isUsed ? 'line-through' : 'none' }}>
                    {item.code}
                  </span>
                  <span style={{ marginLeft: '6px', fontSize: '10px', color: item.isUsed ? '#ef4444' : '#10b981', fontWeight: '500' }}>
                    {item.isUsed ? `[Đã dùng]` : '[Sẵn sàng]'}
                  </span>
                </div>

                <button onClick={() => handleDeleteCode(item.id)} className="btn-danger-crafted">
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
