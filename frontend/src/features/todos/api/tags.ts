import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface Tag {
  id: string;
  user_id: string;
  name: string;
  color: string | null;
  created_at: string;
  updated_at: string;
}

interface TagListResponse {
  items: Tag[];
  total: number;
}

interface CreateTagRequest {
  name: string;
  color?: string;
}

interface UpdateTagRequest {
  name?: string;
  color?: string;
}

// ── Queries ──────────────────────────────────────────────────────────────────

export function useTags() {
  return useQuery({
    queryKey: ["tags"],
    queryFn: async (): Promise<TagListResponse> => {
      const response = await api.get("/tags");
      return response.data;
    },
  });
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export function useCreateTag() {
  return useMutation({
    mutationFn: async (data: CreateTagRequest): Promise<Tag> => {
      const response = await api.post("/tags", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      toast.success("Tag created!");
    },
    onError: (error: unknown) => {
      const msg =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to create tag";
      toast.error(msg);
    },
  });
}

export function useUpdateTag() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateTagRequest;
    }): Promise<Tag> => {
      const response = await api.patch(`/tags/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      toast.success("Tag updated!");
    },
    onError: () => toast.error("Failed to update tag"),
  });
}

export function useDeleteTag() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/tags/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      queryClient.invalidateQueries({ queryKey: ["todos"], exact: false });
      toast.success("Tag deleted!");
    },
    onError: () => toast.error("Failed to delete tag"),
  });
}

export function useAttachTag() {
  return useMutation({
    mutationFn: async ({
      tagId,
      todoId,
    }: {
      tagId: string;
      todoId: string;
    }): Promise<void> => {
      await api.post(`/tags/${tagId}/todos/${todoId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"], exact: false });
    },
    onError: () => toast.error("Failed to attach tag"),
  });
}

export function useDetachTag() {
  return useMutation({
    mutationFn: async ({
      tagId,
      todoId,
    }: {
      tagId: string;
      todoId: string;
    }): Promise<void> => {
      await api.delete(`/tags/${tagId}/todos/${todoId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todos"], exact: false });
    },
    onError: () => toast.error("Failed to detach tag"),
  });
}

export function useBulkUpdateStatus() {
  return useMutation({
    mutationFn: async ({
      todo_ids,
      completed,
    }: {
      todo_ids: string[];
      completed: boolean;
    }): Promise<{ updated: number; completed: boolean }> => {
      const response = await api.patch("/todos/bulk-status", {
        todo_ids,
        completed,
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["todos"], exact: false });
      toast.success(
        `${data.updated} todos marked ${data.completed ? "complete" : "active"}!`
      );
    },
    onError: () => toast.error("Failed to bulk update todos"),
  });
}
