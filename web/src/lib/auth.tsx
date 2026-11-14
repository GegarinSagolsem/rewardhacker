import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from './api'
import type { Me, Role } from './types'

interface AuthState {
  token: string | null
  me: Me | undefined
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [token, setToken] = useState(tokenStore.get)

  const logout = useCallback(() => {
    tokenStore.set(null)
    setToken(null)
    qc.clear()
  }, [qc])

  useEffect(() => setUnauthorizedHandler(logout), [logout])

  const meQuery = useQuery({ queryKey: ['me', token], queryFn: api.me, enabled: !!token, staleTime: 30_000 })

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password)
    tokenStore.set(access_token)
    setToken(access_token)
  }, [])

  const register = useCallback(
    async (email: string, password: string) => {
      await api.register(email, password)
      await login(email, password)
    },
    [login],
  )

  const value = useMemo<AuthState>(
    () => ({ token, me: meQuery.data, loading: !!token && meQuery.isPending, login, register, logout }),
    [token, meQuery.data, meQuery.isPending, login, register, logout],
  )
  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth(): AuthState {
  const ctx = use(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}

const RANK: Record<Role, number> = { viewer: 0, reviewer: 1, admin: 2 }
export const atLeast = (role: Role | undefined, min: Role) => !!role && RANK[role] >= RANK[min]
