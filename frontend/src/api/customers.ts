import apiClient from './client';
import type {
  Customer,
  CustomerCreateRequest,
  CustomerUpdateRequest,
  MessageResponse,
} from '@/types';

export async function listCustomers(): Promise<Customer[]> {
  const resp = await apiClient.get<Customer[]>('/customers');
  return resp.data;
}

export async function getCustomer(id: string): Promise<Customer> {
  const resp = await apiClient.get<Customer>(`/customers/${id}`);
  return resp.data;
}

export async function createCustomer(data: CustomerCreateRequest): Promise<Customer> {
  const resp = await apiClient.post<Customer>('/customers', data);
  return resp.data;
}

export async function updateCustomer(
  id: string,
  data: CustomerUpdateRequest
): Promise<Customer> {
  const resp = await apiClient.patch<Customer>(`/customers/${id}`, data);
  return resp.data;
}

export async function deleteCustomer(id: string): Promise<MessageResponse> {
  const resp = await apiClient.delete<MessageResponse>(`/customers/${id}`);
  return resp.data;
}
