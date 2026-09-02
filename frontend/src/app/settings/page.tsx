'use client';

import { useEffect, useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { Card, Spinner, ErrorBanner, RoleBadge, Badge, Button } from '@/components/ui';
import { getMyWorkspace, listWorkspaceUsers, deleteWorkspaceUser } from '@/api/workspace';
import type { Workspace, WorkspaceUser } from '@/types';
import { AxiosError } from 'axios';
import { useAuth } from '@/context/AuthContext';

export default function SettingsPage() {
  const { role, user } = useAuth();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [ws, us] = await Promise.all([getMyWorkspace(), listWorkspaceUsers()]);
        setWorkspace(ws);
        setUsers(us);
      } catch (err) {
        if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleDeleteUser = async (userId: string) => {
    if (!confirm('Remove this user from the workspace?')) return;
    setDeletingId(userId);
    try {
      await deleteWorkspaceUser(userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
    } catch (err) {
      if (err instanceof AxiosError) setError(err.response?.data?.detail ?? err.message);
    } finally {
      setDeletingId(null);
    }
  };

  const isOwner = role === 'OWNER';

  return (
    <ProtectedRoute>
      <AppLayout title="Settings">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-slate-900">Settings</h2>
          <p className="text-sm text-slate-500">Manage your workspace and team.</p>
        </div>

        {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

        {loading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : (
          <div className="space-y-6 max-w-2xl">
            {/* Workspace Info */}
            {workspace && (
              <Card className="p-6">
                <h3 className="text-sm font-semibold text-slate-700 mb-4 pb-3 border-b border-slate-100">
                  Workspace
                </h3>
                <dl className="space-y-3">
                  <div className="flex justify-between">
                    <dt className="text-sm text-slate-500">Name</dt>
                    <dd className="text-sm font-medium text-slate-800">{workspace.name}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-sm text-slate-500">Slug</dt>
                    <dd className="text-sm font-mono text-slate-600">{workspace.slug}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-sm text-slate-500">ID</dt>
                    <dd className="text-xs font-mono text-slate-400 truncate max-w-[240px]">{workspace.id}</dd>
                  </div>
                </dl>
              </Card>
            )}

            {/* Current User */}
            {user && (
              <Card className="p-6">
                <h3 className="text-sm font-semibold text-slate-700 mb-4 pb-3 border-b border-slate-100">
                  My Account
                </h3>
                <dl className="space-y-3">
                  <div className="flex justify-between">
                    <dt className="text-sm text-slate-500">Name</dt>
                    <dd className="text-sm font-medium text-slate-800">{user.full_name}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-sm text-slate-500">Email</dt>
                    <dd className="text-sm text-slate-600">{user.email}</dd>
                  </div>
                  <div className="flex justify-between items-center">
                    <dt className="text-sm text-slate-500">Role</dt>
                    <dd><RoleBadge role={user.role} /></dd>
                  </div>
                  <div className="flex justify-between items-center">
                    <dt className="text-sm text-slate-500">Status</dt>
                    <dd>
                      <Badge color={user.is_active ? 'green' : 'red'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </dd>
                  </div>
                </dl>
              </Card>
            )}

            {/* Team Members */}
            <Card>
              <div className="px-5 py-4 border-b border-slate-100">
                <h3 className="text-sm font-semibold text-slate-700">Team Members ({users.length})</h3>
                {!isOwner && (
                  <p className="text-xs text-slate-400 mt-0.5">
                    Only OWNER can add or remove members.
                  </p>
                )}
              </div>
              <div className="divide-y divide-slate-50">
                {users.map((u) => (
                  <div key={u.id} className="flex items-center justify-between px-5 py-3.5">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-slate-800">{u.full_name}</p>
                        {u.id === user?.id && (
                          <span className="text-xs text-slate-400">(you)</span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500">{u.email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <RoleBadge role={u.role} />
                      {isOwner && u.id !== user?.id && (
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={deletingId === u.id}
                          onClick={() => handleDeleteUser(u.id)}
                          className="text-red-500 hover:text-red-700"
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}
      </AppLayout>
    </ProtectedRoute>
  );
}
