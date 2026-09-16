import { useState } from "react";
import { Plus, LogOut, Tag, CheckSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useTodos } from "../api/todos";
import type { TodoFiltersParams } from "../api/todos";
import { useBulkUpdateStatus } from "../api/tags";
import { TodoList } from "./TodoList";
import { TodoForm } from "./TodoForm";
import { TodoFilter } from "./TodoFilter";
import type { TodoFilters } from "./TodoFilter";
import { TagManager } from "./TagManager";
import { useAuth } from "@/features/auth/hooks/useAuth";
import type { Todo } from "../api/todos";

const EMPTY_FILTERS: TodoFilters = {};

export function TodoPage() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showTagManager, setShowTagManager] = useState(false);
  const [filters, setFilters] = useState<TodoFilters>(EMPTY_FILTERS);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const queryParams: TodoFiltersParams = {
    keyword: filters.keyword,
    status: filters.status || undefined,
    tag_id: filters.tag_id,
    date_from: filters.date_from,
    date_to: filters.date_to,
  };

  const { data, isLoading, error } = useTodos(queryParams);
  const { user, logout } = useAuth();
  const bulkUpdate = useBulkUpdateStatus();

  const todos = data?.items ?? [];

  const allSelected =
    todos.length > 0 && todos.every((t) => selectedIds.has(t.id));

  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(todos.map((t) => t.id)));
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBulkAction = (completed: boolean) => {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    bulkUpdate.mutate(
      { todo_ids: ids, completed },
      { onSuccess: () => setSelectedIds(new Set()) }
    );
  };

  const handleClearFilters = () => {
    setFilters(EMPTY_FILTERS);
  };

  return (
    <div className="min-h-screen bg-muted/40">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Todo App</h1>
            {user && (
              <p className="text-sm text-muted-foreground">{user.email}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowTagManager(true)}
            >
              <Tag className="h-4 w-4 mr-2" />
              Tags
            </Button>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut className="h-4 w-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-4">
        {/* Filter bar */}
        <TodoFilter
          filters={filters}
          onChange={setFilters}
          onClear={handleClearFilters}
        />

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">My Todos</CardTitle>
            <Button size="sm" onClick={() => setShowCreateForm(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add Todo
            </Button>
          </CardHeader>
          <Separator />
          <CardContent className="pt-4">
            {/* Bulk actions bar */}
            {todos.length > 0 && (
              <div className="flex items-center gap-2 mb-3 pb-3 border-b">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={handleSelectAll}
                  className="h-4 w-4 cursor-pointer"
                  title={allSelected ? "Deselect all" : "Select all"}
                />
                <span className="text-xs text-muted-foreground">
                  {selectedIds.size > 0
                    ? `${selectedIds.size} selected`
                    : "Select all"}
                </span>
                {selectedIds.size > 0 && (
                  <div className="flex items-center gap-1 ml-auto">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => handleBulkAction(true)}
                      disabled={bulkUpdate.isPending}
                    >
                      <CheckSquare className="h-3 w-3 mr-1" />
                      Mark done
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => handleBulkAction(false)}
                      disabled={bulkUpdate.isPending}
                    >
                      Mark active
                    </Button>
                  </div>
                )}
              </div>
            )}

            {isLoading && (
              <div className="text-center py-12 text-muted-foreground">
                Loading todos...
              </div>
            )}

            {error && (
              <div className="text-center py-12 text-destructive">
                Failed to load todos. Please try again.
              </div>
            )}

            {data && (
              <TodoList
                todos={todos}
                selectedIds={selectedIds}
                onToggleSelect={handleToggleSelect}
              />
            )}

            {data && data.total > 0 && (
              <div className="mt-4 text-center text-sm text-muted-foreground">
                Showing {data.items.length} of {data.total} todos
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Dialogs */}
      <TodoForm
        mode="create"
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
      />
      <TagManager
        open={showTagManager}
        onClose={() => setShowTagManager(false)}
      />
    </div>
  );
}
