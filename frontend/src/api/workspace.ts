import apiClient from './client';
import type { Workspace, WorkspaceUser, Member } from '@/types';

export async function getMyWorkspace(): Promise<Workspace> {
  const resp = await apiClient.get<Workspace>('/workspaces/me');
  return resp.data;
}

export async function updateMyWorkspace(data: {
  name?: string;
  slug?: string;
}): Promise<Workspace> {
  const resp = await apiClient.patch<Workspace>('/workspaces/me', data);
  return resp.data;
}

export async function listWorkspaceUsers(): Promise<WorkspaceUser[]> {
  const resp = await apiClient.get<WorkspaceUser[]>('/workspaces/users');
  return resp.data;
}

export async function listWorkspaceMembers(workspaceId: string): Promise<Member[]> {
  const resp = await apiClient.get<Member[]>(`/workspaces/${workspaceId}/members`);
  return resp.data;
}

export async function createWorkspaceUser(data: {
  full_name: string;
  email: string;
  password: string;
  role?: string;
}): Promise<WorkspaceUser> {
  const resp = await apiClient.post<WorkspaceUser>('/workspaces/users', data);
  return resp.data;
}

export async function deleteWorkspaceUser(userId: string): Promise<{ message: string }> {
  const resp = await apiClient.delete<{ message: string }>(`/workspaces/users/${userId}`);
  return resp.data;
}
