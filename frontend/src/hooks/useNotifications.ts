import { useState, useEffect, useCallback, useRef } from 'react'
import api, { extractResults, type PaginatedResponse } from '../api/client'

// Mirrors the backend NotificationSerializer (apps/notifications/serializers.py).
export interface Notification {
  id: string
  title: string
  body: string
  notif_type: string
  notif_type_display?: string
  level: 'INFO' | 'WARN' | 'CRITICAL'
  level_display?: string
  channel?: string
  link: string | null
  read: boolean
  created_at: string
}

const POLL_INTERVAL_MS = 30_000

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchUnreadCount = useCallback(async () => {
    try {
      const data = await api.get<{ unread_count: number }>('/notifications/unread_count/')
      setUnreadCount(data?.unread_count ?? 0)
    } catch {
      // Silently fail — notifications are non-critical
    }
  }, [])

  const fetchNotifications = useCallback(async () => {
    try {
      // Backend list is paginated ({count, results}) — normalize to an array.
      const data = await api.get<Notification[] | PaginatedResponse<Notification>>('/notifications/?read=false')
      setNotifications(extractResults(data))
    } catch {
      // Silently fail — notifications are non-critical
    }
  }, [])

  const poll = useCallback(() => {
    fetchNotifications()
    fetchUnreadCount()
  }, [fetchNotifications, fetchUnreadCount])

  const startPolling = useCallback(() => {
    if (intervalRef.current) return
    poll()
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS)
  }, [poll])

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => {
    startPolling()
    return () => stopPolling()
  }, [startPolling, stopPolling])

  const markRead = useCallback(async (id: number | string) => {
    // Optimistically drop the item from the unread list, then confirm server-side.
    setNotifications((prev) => prev.filter((n) => n.id !== id))
    setUnreadCount((prev) => Math.max(0, prev - 1))
    try {
      await api.patch(`/notifications/${id}/read/`)
    } catch {
      // Item will reappear on next poll if the PATCH failed
    }
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      // Backend exposes PATCH /api/notifications/read_all/
      await api.patch('/notifications/read_all/')
      setNotifications([])
      setUnreadCount(0)
    } catch {
      // Silently fail
    }
  }, [])

  const refetch = useCallback(() => {
    poll()
  }, [poll])

  return { notifications, unreadCount, markRead, markAllRead, refetch }
}
