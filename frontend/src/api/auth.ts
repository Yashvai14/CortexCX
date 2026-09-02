import axios from 'axios';
import apiClient, { setAccessToken } from './client';
import type { TokenResponse, User } from '@/types';

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

// Login uses application/x-www-form-urlencoded (OAuth2PasswordRequestForm)
export async function login(email: string, password: string): Promise<{ tokens: TokenResponse; user: User }> {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const resp = await axios.post<TokenResponse>(
    `${BASE_URL}/auth/login`,
    formData.toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );

  const tokens = resp.data;
  // Store access token in memory
  setAccessToken(tokens.access_token);
  // Store refresh token in localStorage
  if (typeof window !== 'undefined') {
    localStorage.setItem('cortex_refresh_token', tokens.refresh_token);
  }

  // Fetch user profile
  const userResp = await apiClient.get<User>('/auth/me');
  return { tokens, user: userResp.data };
}

export async function logout(refreshToken: string): Promise<void> {
  try {
    await apiClient.post('/auth/logout', { refresh_token: refreshToken });
  } finally {
    setAccessToken(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('cortex_refresh_token');
    }
  }
}

export async function getMe(): Promise<User> {
  const resp = await apiClient.get<User>('/auth/me');
  return resp.data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const resp = await apiClient.post<TokenResponse>('/auth/refresh', {
    refresh_token: refreshToken,
  });
  return resp.data;
}
