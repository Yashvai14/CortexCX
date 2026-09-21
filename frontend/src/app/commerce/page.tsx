'use client';

import { useEffect, useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Card, SkeletonCard, ErrorBanner, Badge } from '@/components/ui';
import {
  listProducts,
  listOrders,
  listPolicies,
  listCoupons,
  type ProductItem,
  type OrderSummary,
  type PolicyItem,
  type CouponItem,
} from '@/api/commerce';
import { AxiosError } from 'axios';

export default function CommercePage() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [coupons, setCoupons] = useState<CouponItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'products' | 'orders' | 'policies' | 'coupons'>('products');

  const load = async () => {
    try {
      const [p, o, pol, c] = await Promise.all([
        listProducts(),
        listOrders(),
        listPolicies(),
        listCoupons(),
      ]);
      setProducts(p);
      setOrders(o);
      setPolicies(pol);
      setCoupons(c);
    } catch (err) {
      if (err instanceof AxiosError) {
        setError(err.response?.data?.detail ?? err.message);
      } else {
        setError('Failed to load commerce data');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <ProtectedRoute>
      <AppLayout title="D2C Commerce & Operations">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-slate-900">Commerce Catalog & Policies</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Authoritative product inventory, order fulfillment, refund policies, and promotional discount codes.
          </p>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {/* Tab Selector */}
        <div className="flex border-b border-slate-200 mb-6 gap-6">
          <button
            onClick={() => setActiveTab('products')}
            className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'products'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Products & Inventory ({products.length})
          </button>
          <button
            onClick={() => setActiveTab('orders')}
            className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'orders'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Orders & Tracking ({orders.length})
          </button>
          <button
            onClick={() => setActiveTab('policies')}
            className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'policies'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Store Policies ({policies.length})
          </button>
          <button
            onClick={() => setActiveTab('coupons')}
            className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === 'coupons'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Promotions & Coupons ({coupons.length})
          </button>
        </div>

        {loading ? (
          <SkeletonCard />
        ) : activeTab === 'products' ? (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-5 py-3">Product</th>
                    <th className="px-5 py-3">SKU</th>
                    <th className="px-5 py-3">Category</th>
                    <th className="px-5 py-3">Price</th>
                    <th className="px-5 py-3">Stock Available</th>
                    <th className="px-5 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {products.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                        No products found in catalog.
                      </td>
                    </tr>
                  ) : (
                    products.map((p) => (
                      <tr key={p.id} className="hover:bg-slate-50/50">
                        <td className="px-5 py-3.5 font-medium text-slate-900">{p.name}</td>
                        <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{p.sku}</td>
                        <td className="px-5 py-3.5 text-slate-600">{p.category || 'General'}</td>
                        <td className="px-5 py-3.5 font-semibold text-slate-900">${p.price.toFixed(2)}</td>
                        <td className="px-5 py-3.5 font-mono text-slate-700">{p.quantity_available} units</td>
                        <td className="px-5 py-3.5">
                          <Badge variant={p.in_stock ? 'success' : 'danger'}>
                            {p.in_stock ? 'IN STOCK' : 'OUT OF STOCK'}
                          </Badge>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        ) : activeTab === 'orders' ? (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-5 py-3">Order Number</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Total Amount</th>
                    <th className="px-5 py-3">Carrier & Tracking</th>
                    <th className="px-5 py-3">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {orders.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-8 text-center text-slate-400">
                        No orders recorded yet.
                      </td>
                    </tr>
                  ) : (
                    orders.map((o) => (
                      <tr key={o.id} className="hover:bg-slate-50/50">
                        <td className="px-5 py-3.5 font-mono font-medium text-indigo-600">{o.order_number}</td>
                        <td className="px-5 py-3.5">
                          <Badge variant={o.status === 'delivered' ? 'success' : 'info'}>
                            {o.status.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-5 py-3.5 font-semibold text-slate-900">${o.total_amount.toFixed(2)}</td>
                        <td className="px-5 py-3.5 text-xs text-slate-600">
                          {o.carrier || 'Standard'} {o.tracking_number ? `(${o.tracking_number})` : ''}
                        </td>
                        <td className="px-5 py-3.5 text-xs text-slate-400">
                          {new Date(o.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        ) : activeTab === 'policies' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {policies.length === 0 ? (
              <p className="text-sm text-slate-400">No store policies configured.</p>
            ) : (
              policies.map((pol) => (
                <Card key={pol.id} className="p-5">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-slate-900">{pol.title}</h3>
                    <Badge variant="info">{pol.policy_type.toUpperCase()}</Badge>
                  </div>
                  <p className="text-xs text-slate-600 whitespace-pre-wrap leading-relaxed">{pol.content}</p>
                </Card>
              ))
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {coupons.length === 0 ? (
              <p className="text-sm text-slate-400">No active promotional coupons.</p>
            ) : (
              coupons.map((c) => (
                <Card key={c.id} className="p-5 border-dashed border-2 border-indigo-200 bg-indigo-50/30">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-base font-bold text-indigo-700">{c.code}</span>
                    <Badge variant="success">ACTIVE</Badge>
                  </div>
                  <p className="text-sm font-semibold text-slate-800">
                    {c.discount_value}{c.discount_type === 'percentage' ? '% OFF' : ' $ OFF'}
                  </p>
                </Card>
              ))
            )}
          </div>
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}
