import React, { useState, useEffect } from 'react'

// Get API URL from runtime config or fallback to default
const getApiUrl = (): string => {
  if (typeof window !== 'undefined') {
    // Check if we have runtime config
    if ((window as any).APP_CONFIG?.API_URL) {
      const configUrl = (window as any).APP_CONFIG.API_URL;
      // If accessing from browser (localhost), convert cluster URLs to localhost
      if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        if (configUrl.includes('backend:8000') || configUrl.includes('backend.fullstack')) {
          return 'http://localhost:8000';
        }
      }
      return configUrl;
    }
    // Fallback: if accessing from localhost, use localhost backend
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return 'http://localhost:8000';
    }
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
};

const API_URL = getApiUrl();

interface Todo {
  id: number
  title: string
  completed: boolean
  created_at: string
}

function App() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [newTodo, setNewTodo] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState<boolean>(false)

  useEffect(() => {
    fetchTodos()
  }, [])

  const fetchTodos = async (): Promise<void> => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`${API_URL}/todos`)
      if (!response.ok) {
        throw new Error(`Failed to fetch todos: ${response.statusText}`)
      }
      const data: Todo[] = await response.json()
      setTodos(data)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      console.error('Error fetching todos:', err)
    } finally {
      setLoading(false)
    }
  }

  const createTodo = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault()
    if (!newTodo.trim()) return

    try {
      setSubmitting(true)
      setError(null)
      const response = await fetch(`${API_URL}/todos`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: newTodo.trim() }),
      })

      if (!response.ok) {
        throw new Error(`Failed to create todo: ${response.statusText}`)
      }

      const createdTodo: Todo = await response.json()
      setTodos([createdTodo, ...todos])
      setNewTodo('')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      console.error('Error creating todo:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const deleteTodo = async (id: number): Promise<void> => {
    try {
      setError(null)
      const response = await fetch(`${API_URL}/todos/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error(`Failed to delete todo: ${response.statusText}`)
      }

      setTodos(todos.filter((todo) => todo.id !== id))
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      console.error('Error deleting todo:', err)
    }
  }

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleString()
  }

  return (
    <div className="app">
      <h1>TODO App</h1>

      {error && <div className="error">Error: {error}</div>}

      <form onSubmit={createTodo} className="todo-form">
        <input
          type="text"
          value={newTodo}
          onChange={(e) => setNewTodo(e.target.value)}
          placeholder="Add a new todo..."
          className="todo-input"
          disabled={submitting}
        />
        <button type="submit" className="todo-button" disabled={submitting}>
          {submitting ? 'Adding...' : 'Add'}
        </button>
      </form>

      {loading ? (
        <div className="loading">Loading todos...</div>
      ) : todos.length === 0 ? (
        <div className="empty">No todos yet. Add one above!</div>
      ) : (
        <ul className="todo-list">
          {todos.map((todo) => (
            <li key={todo.id} className="todo-item">
              <div className="todo-item-content">
                <div className="todo-item-title">{todo.title}</div>
                <div className="todo-item-date">
                  Created: {formatDate(todo.created_at)}
                </div>
              </div>
              <button
                onClick={() => deleteTodo(todo.id)}
                className="delete-button"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default App
