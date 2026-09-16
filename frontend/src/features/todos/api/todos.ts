import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface Todo {
  id: string;
  title: string;
  description: string | null;
  completed: boolean;
  user_id: string;
  created_at: string;
  updated_at: string;
}

interface TodoListResponse {
  items: Todo[];
  total: number;
  page: number;
  size: number;
}

interface CreateTodoRequest {
  title: string;
  description?: string;
}

interface UpdateTodoRequest {
  title?: string;
  description?: string;
  completed?: boolean;
}


export interface TodoFiltersParams {
  page?: number;
  size?: number;
  status?: string;
  tag_id?: string;
  keyword?: string;
  date_from?: string;
  date_to?: string;
}

export function useTodos(params: TodoFiltersParams = {}) {
  const { page = 1, size = 10000, status, tag_id, keyword, date_from, date_to } = params;
  return useQuery({
    // Bug fix: Include all filter params in query key so different filter
    // combinations have separate cache entries.
    queryKey: ["todos", page, size, status, tag_id, keyword, date_from, date_to],
    queryFn: async (): Promise<TodoListResponse> => {
      const response = await api.get("/todos", {
        params: { page, size, status, tag_id, keyword, date_from, date_to },
      });
      return response.data;
    },
  });
}

export function useCreateTodo() {
  return useMutation({
    mutationFn: async (data: CreateTodoRequest): Promise<Todo> => {
      const response = await api.post("/todos", data);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all todo queries (any page/size combination)
      queryClient.invalidateQueries({ queryKey: ["todos"], exact: false });
      toast.success("Todo created successfully!");
    },
    onError: () => {
      toast.error("Failed to create todo");
    },
  });
}


export function useUpdateTodo() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateTodoRequest;
    }): Promise<Todo> => {
      const response = await api.put(`/todos/${id}`, data);
      return response.data;
    },
    onMutate: async ({ id, data }) => {
      // Cancel outgoing queries (all page/size variants)
      await queryClient.cancelQueries({ queryKey: ["todos"], exact: false });

      // Snapshot previous value
      const previousTodos = queryClient.getQueryData<TodoListResponse>(["todos"]);

      // Optimistically update
      if (previousTodos) {
        queryClient.setQueryData<TodoListResponse>(["todos"], {
          ...previousTodos,
          items: previousTodos.items.map((todo) =>
            todo.id === id ? { ...todo, ...data } : todo
          ),
        });
      }

      return { previousTodos };
    },
    onError: () => {
      toast.error("Failed to update todo");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"], exact: false });
    },
  });
}

export function useDeleteTodo() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/todos/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"], exact: false });
      toast.success("Todo deleted successfully!");
    },
    onError: () => {
      toast.error("Failed to delete todo");
    },
  });
}

export function useToggleTodo() {
  const updateTodo = useUpdateTodo();

  return {
    ...updateTodo,
    mutate: (todo: Todo) => {
      updateTodo.mutate({
        id: todo.id,
        data: { completed: !todo.completed },
      });
    },
  };
}
