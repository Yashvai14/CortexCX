import apiClient from './client';

export interface ProductItem {
  id: string;
  sku: string;
  name: string;
  description?: string;
  price: number;
  currency: string;
  category?: string;
  in_stock: boolean;
  quantity_available: number;
}

export interface OrderSummary {
  id: string;
  order_number: string;
  status: string;
  total_amount: number;
  tracking_number?: string;
  carrier?: string;
  created_at: string;
}

export interface PolicyItem {
  id: string;
  policy_type: string;
  title: string;
  content: string;
  is_active: boolean;
}

export interface CouponItem {
  id: string;
  code: string;
  discount_type: string;
  discount_value: number;
  is_active: boolean;
}

export async function listProducts(query?: string): Promise<ProductItem[]> {
  const resp = await apiClient.get<ProductItem[]>('/commerce/products', {
    params: query ? { query } : {},
  });
  return resp.data;
}

export async function listOrders(): Promise<OrderSummary[]> {
  const resp = await apiClient.get<OrderSummary[]>('/commerce/orders');
  return resp.data;
}

export async function listPolicies(): Promise<PolicyItem[]> {
  const resp = await apiClient.get<PolicyItem[]>('/commerce/policies');
  return resp.data;
}

export async function listCoupons(): Promise<CouponItem[]> {
  const resp = await apiClient.get<CouponItem[]>('/commerce/coupons');
  return resp.data;
}
